"""
Async HTTP fetching, queue management, link extraction, and search fallback.

The fetch() function adds page-level HTML caching (24h TTL) so re-crawling
the same URL within or across sessions doesn't re-hit the network.
"""

import os
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin

import aiohttp
from bs4 import BeautifulSoup

try:
    from serpapi import GoogleSearch  # type: ignore
except Exception:
    try:
        from serpapi.google_search import GoogleSearch  # type: ignore
    except Exception:
        GoogleSearch = None

from utils.cache import get_cache
from utils.crawl._constants import (
    HEADERS,
    SEARCH_FALLBACK_URL_LIMIT,
)
from utils.crawl._utils import (
    get_domain_scope,
    normalize_url,
    sanitize_text_for_llm,
)
from utils.crawl.models import CrawlQueueItem, QueryConstraints
from utils.logger import logger

SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")
HTML_CACHE_TTL = int(os.getenv("HTML_CACHE_TTL_SECONDS", str(24 * 3600)))  # 24 hours


# ── HTTP Fetch (with URL-level HTML cache) ─────────────────────────────────────


async def fetch(session: aiohttp.ClientSession, url: str, timeout: int = 15) -> Optional[str]:
    """
    Fetch a single URL and return its HTML, or None on failure.

    Checks the persistent cache first (key: ``html:<url>``).  On a live fetch,
    successful HTML responses are stored for HTML_CACHE_TTL seconds so the same
    page is never downloaded twice — even across server restarts.
    """
    cache_key = f"html:{url}"
    cache = get_cache()

    cached_html = await cache.get(cache_key)
    if cached_html is not None:
        logger.debug("HTML cache hit: %s", url)
        return cached_html

    try:
        async with session.get(url, headers=HEADERS, timeout=timeout) as r:
            content_type = r.headers.get("content-type", "").lower()
            if r.status == 200 and (
                "text/html" in content_type or "application/xhtml+xml" in content_type
            ):
                html = await r.text()
                await cache.set(cache_key, html, HTML_CACHE_TTL)
                return html
            logger.debug("Skipping %s: status=%s content_type=%s", url, r.status, content_type)
    except Exception as exc:
        logger.debug("Fetch failed for %s: %s", url, exc)

    return None


# ── Queue management ───────────────────────────────────────────────────────────


def pop_next_batch(
    queue: List[CrawlQueueItem],
    visited: Set[str],
    queued_urls: Set[str],
    batch_size: int = 12,
    required_seed_visits_remaining: int = 0,
) -> List[CrawlQueueItem]:
    """
    Pop the next batch of URLs to fetch, prioritising seed URLs first
    until the required seed-visit quota is met.
    """
    queue.sort(key=lambda item: item.priority, reverse=True)
    batch: List[CrawlQueueItem] = []

    # Fill with seeds first (ensures high-priority paths are visited)
    while queue and len(batch) < batch_size and required_seed_visits_remaining > 0:
        idx = next((i for i, item in enumerate(queue) if item.source == "seed"), None)
        if idx is None:
            break
        item = queue.pop(idx)
        queued_urls.discard(item.url)
        if item.url in visited:
            continue
        visited.add(item.url)
        batch.append(item)
        required_seed_visits_remaining -= 1

    # Fill remaining slots from top of queue
    while queue and len(batch) < batch_size:
        item = queue.pop(0)
        queued_urls.discard(item.url)
        if item.url in visited:
            continue
        visited.add(item.url)
        batch.append(item)

    return batch


# ── Link extraction ────────────────────────────────────────────────────────────


def extract_links(html: str, base_url: str) -> List[str]:
    """Extract all internal links from HTML, restricted to the same domain scope."""
    from urllib.parse import urlparse

    soup = BeautifulSoup(html, "lxml")
    base = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(base_url))
    base_scope = get_domain_scope(base_url)
    links: List[str] = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(("#", "mailto:", "tel:")):
            continue
        absolute = urljoin(base, href)
        if get_domain_scope(absolute) == base_scope:
            links.append(normalize_url(absolute))

    return list(set(links))


# ── SerpAPI fallback ───────────────────────────────────────────────────────────


def search_fallback_urls(
    domain_url: str,
    user_query: Optional[str],
    constraints: QueryConstraints,
) -> List[Dict[str, str]]:
    """
    Use site-restricted SerpAPI search to find likely funding pages when
    the structural BFS crawl returns weak results.

    Only called when fetched_page_results is empty or avg_score < 20.
    """
    if GoogleSearch is None or not SERPAPI_KEY:
        return []

    scope = get_domain_scope(domain_url)
    if not scope:
        return []

    subject_terms = constraints.subject_terms[:2]
    degree_terms = constraints.degree_terms[:2] or ["phd", "doctoral"]
    query_variants = [
        f"site:{scope} {' '.join(degree_terms)} funding",
        f"site:{scope} {' '.join(degree_terms)} scholarship",
    ]
    if subject_terms:
        query_variants.append(f"site:{scope} {' '.join(subject_terms)} {' '.join(degree_terms)}")
        query_variants.append(
            f"site:{scope} {' '.join(subject_terms)} funding scholarship research"
        )
    if user_query:
        query_variants.append(f"site:{scope} {user_query}")

    url_entries: List[Dict[str, str]] = []
    seen: Set[str] = set()
    for query in query_variants[:4]:
        try:
            search = GoogleSearch({"q": query, "api_key": SERPAPI_KEY, "num": 5})
            results = search.get_dict()
        except Exception as exc:
            logger.debug("Fallback search failed for %s: %s", query, exc)
            continue

        for result in results.get("organic_results", []) or []:
            link = normalize_url(str(result.get("link", "") or ""))
            if not link or get_domain_scope(link) != scope or link in seen:
                continue
            seen.add(link)
            url_entries.append(
                {
                    "url": link,
                    "title": sanitize_text_for_llm(str(result.get("title", "") or "")),
                    "snippet": sanitize_text_for_llm(str(result.get("snippet", "") or "")),
                }
            )
            if len(url_entries) >= SEARCH_FALLBACK_URL_LIMIT:
                return url_entries

    return url_entries
