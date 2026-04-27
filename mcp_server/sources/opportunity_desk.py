"""Opportunity Desk — global scholarships, fellowships, and competitions scraped from WordPress search."""

import logging
import re

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

_SEARCH = "https://opportunitydesk.org/"
_DATE_RE = re.compile(r"/(\d{4}/\d{2}/\d{2})/")


async def search(query: str, limit: int = 10) -> list[dict]:
    params = {"s": query}

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        resp = await client.get(_SEARCH, params=params)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    articles = soup.select("article")[:limit]

    results = []
    for article in articles:
        title_tag = article.select_one(
            "h2.is-title a, h2.post-title a, h2.entry-title a, h1.entry-title a"
        )
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        url = title_tag.get("href", "")

        # Extract date from the WordPress permalink /YYYY/MM/DD/
        date = ""
        m = _DATE_RE.search(url)
        if m:
            date = m.group(1).replace("/", "-")

        excerpt_tag = article.select_one(".excerpt, .entry-summary, .entry-content")
        summary = excerpt_tag.get_text(" ", strip=True)[:300] if excerpt_tag else ""

        results.append(
            {
                "title": title,
                "deadline": date,
                "url": url,
                "summary": summary,
                "source": "Opportunity Desk",
            }
        )

    log.info("OpportunityDesk search(%r) → %d results", query, len(results))
    log.debug("OpportunityDesk results: %s", results)
    return results
