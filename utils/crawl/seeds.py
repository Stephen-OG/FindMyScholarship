"""
Seed domain queue building for university crawls.

Starts crawls from domain root URLs; link priority during crawl is
determined by score_link_priority in scorer.py using extracted query terms.
"""

from typing import List, Set
from urllib.parse import urlparse

from utils.crawl._constants import (
    MAX_AUXILIARY_SEED_DOMAINS,
    MAX_TOTAL_INITIAL_QUEUE,
)
from utils.crawl._utils import (
    get_domain_scope,
    normalize_url,
)
from utils.crawl.models import CrawlQueueItem


def build_initial_queue(domain_url: str) -> List[CrawlQueueItem]:
    """Build the starting BFS queue from the domain root."""
    return [CrawlQueueItem(url=normalize_url(domain_url), priority=0, source="root")]


def generate_auxiliary_seed_domains(domain_url: str) -> List[str]:
    """Probe common university subdomains that may host scholarship info."""
    normalized = normalize_url(domain_url)
    parsed = urlparse(normalized)
    scope = get_domain_scope(normalized)
    if not scope:
        return []

    current_host = parsed.netloc.lower().replace(":80", "").replace(":443", "")
    auxiliary: List[str] = []
    seen: Set[str] = set()
    for prefix in [
        "ask",
        "scholarships",
        "funding",
        "finance",
        "financialaid",
        "research",
        "graduate",
        "graduateschool",
    ]:
        host = f"{prefix}.{scope}"
        if host == current_host:
            continue
        url = f"{parsed.scheme}://{host}"
        if url not in seen:
            auxiliary.append(url)
            seen.add(url)
    return auxiliary


def build_multi_domain_queue(
    domain_url: str,
    extra_seed_domains: List[str],
    max_pages: int,
) -> tuple[List[CrawlQueueItem], Set[str], int]:
    """
    Build the combined initial queue for a domain + its auxiliary subdomains.

    Returns:
        (queue, queued_url_set, required_seed_visits)
    """
    to_visit = build_initial_queue(domain_url)

    # Deduplicate auxiliary domains
    extra = []
    seen_extra: Set[str] = set()
    for ed in (extra_seed_domains or []) + generate_auxiliary_seed_domains(domain_url):
        norm = normalize_url(ed)
        if norm and norm != normalize_url(domain_url) and norm not in seen_extra:
            seen_extra.add(norm)
            extra.append(norm)
            if len(extra) >= MAX_AUXILIARY_SEED_DOMAINS:
                break

    for ed_url in extra:
        to_visit.append(CrawlQueueItem(url=normalize_url(ed_url), priority=220, source="seed"))

    to_visit.sort(key=lambda item: item.priority, reverse=True)
    to_visit = to_visit[:MAX_TOTAL_INITIAL_QUEUE]

    queued_url_set: Set[str] = {item.url for item in to_visit}
    total_seeds = sum(1 for item in to_visit if item.source == "seed")
    required_seed_visits = min((total_seeds + 1) // 2, max_pages)

    return to_visit, queued_url_set, required_seed_visits
