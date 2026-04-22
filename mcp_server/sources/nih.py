"""NIH Reporter API — NIH-funded biomedical and health research grants."""

import httpx

_BASE = "https://api.reporter.nih.gov/v2/projects/search"
_DETAIL = "https://reporter.nih.gov/project-details/{id}"


async def search(query: str, limit: int = 10) -> list[dict]:
    payload = {
        "criteria": {"project_terms": query},
        "limit": limit,
        "offset": 0,
        "sort_field": "project_start_date",
        "sort_order": "desc",
    }
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(_BASE, json=payload)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for proj in data.get("results", []):
        pis = proj.get("principal_investigators") or []
        pi_name = pis[0].get("full_name", "") if pis else ""
        award = proj.get("award_amount")
        results.append({
            "title": proj.get("project_title", ""),
            "funder": "NIH",
            "organization": proj.get("organization", {}).get("org_name", ""),
            "pi": pi_name,
            "fiscal_year": str(proj.get("fiscal_year", "")),
            "amount": f"${award:,}" if award else "",
            "url": _DETAIL.format(id=proj.get("appl_id", "")),
            "summary": (proj.get("abstract_text") or "")[:300],
            "source": "NIH Reporter",
        })
    return results
