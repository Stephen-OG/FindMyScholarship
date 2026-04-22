"""Grants.gov REST API — US federal scholarships, fellowships, and research grants."""

import httpx

_BASE = "https://apply07.grants.gov/grantsws/rest/opportunities/search/"
_DETAIL = "https://www.grants.gov/search-results-detail/{id}"


async def search(query: str, rows: int = 10) -> list[dict]:
    payload = {
        "keyword": query,
        "oppStatuses": "forecasted|posted",
        "rows": rows,
        "sortBy": "openDate|desc",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(_BASE, json=payload)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for opp in data.get("oppHits", []):
        ceiling = opp.get("awardCeiling")
        results.append({
            "title": opp.get("title", ""),
            "funder": opp.get("agencyName", ""),
            "deadline": opp.get("closeDate") or "See listing",
            "amount": f"${ceiling:,}" if ceiling else "",
            "url": _DETAIL.format(id=opp.get("id", "")),
            "summary": (opp.get("synopsis") or "")[:300],
            "source": "Grants.gov",
        })
    return results
