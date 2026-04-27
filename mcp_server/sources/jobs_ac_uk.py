"""jobs.ac.uk — UK academic PhD studentships and research positions.

Scrapes the dedicated PhD search endpoint which lists funded PhD studentships
from UK and international universities.

Note: findaphd.com (the original target) is fully blocked by Cloudflare's
Turnstile challenge and cannot be reached by any automated HTTP client.
jobs.ac.uk covers identical content (funded PhD studentships) and works
with plain HTTP.
"""

import re

import httpx
from bs4 import BeautifulSoup

_SEARCH = "https://www.jobs.ac.uk/search/phds"
_BASE_URL = "https://www.jobs.ac.uk"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}
# Strip "Salary: " / "Date Placed: " label text
_LABEL_RE = re.compile(r"^(salary|date placed)\s*:\s*", re.I)


def _clean(text: str) -> str:
    return " ".join(text.split())


def _extract_field(card, keyword: str) -> str:
    """Return text from the div that starts with `keyword:` inside a card."""
    for div in card.find_all("div"):
        raw = div.get_text(" ", strip=True)
        if raw.lower().startswith(keyword.lower() + ":"):
            return _clean(_LABEL_RE.sub("", raw))
    return ""


async def search(query: str, limit: int = 10) -> list[dict]:
    params = {"keywords": query[:200], "sort": "date", "page": 1}

    async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=_HEADERS) as client:
        resp = await client.get(_SEARCH, params=params)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    cards = soup.select(".j-search-result__text")[:limit]

    results = []
    for card in cards:
        title_tag = card.select_one("a")
        if not title_tag:
            continue

        title = _clean(title_tag.get_text())
        href = title_tag.get("href", "")
        url = _BASE_URL + href if href.startswith("/") else href

        university = _clean(
            card.select_one(".j-search-result__employer b, .j-search-result__employer").get_text()
            if card.select_one(".j-search-result__employer")
            else ""
        )
        department = _clean(
            card.select_one(".j-search-result__department").get_text()
            if card.select_one(".j-search-result__department")
            else ""
        )
        stipend_raw = _clean(
            card.select_one(".j-search-result__info").get_text()
            if card.select_one(".j-search-result__info")
            else ""
        )
        stipend = re.sub(r"^salary\s*:\s*", "", stipend_raw, flags=re.I)

        location = _extract_field(card, "location")
        date_placed = _extract_field(card, "date placed")

        summary_parts = [p for p in [department, location] if p]
        summary = " · ".join(summary_parts)

        results.append(
            {
                "title": title,
                "organization": university,
                "amount": stipend,
                "deadline": date_placed,
                "url": url,
                "summary": summary,
                "source": "jobs.ac.uk",
            }
        )

    return results
