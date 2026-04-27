"""NIH Reporter API — NIH student fellowships and training grants (not active projects)."""

import httpx

_BASE = "https://api.reporter.nih.gov/v2/projects/search"
_DETAIL = "https://reporter.nih.gov/project-details/{id}"

# Activity codes that represent student/trainee funding opportunities:
# F31 = Predoctoral NRSA Individual Fellowship
# F32 = Postdoctoral NRSA Individual Fellowship
# T32 = Institutional Research Training Grant (funds PhD/postdoc slots)
# T34 = Undergraduate NRSA Institutional Research Training Grant
# F99/K00 = Predoctoral to Postdoctoral Fellow Transition Award
# K99/R00 = Pathway to Independence (early postdoc → faculty)
_TRAINEE_ACTIVITY_CODES = ["F31", "F32", "T32", "T34", "F99", "K00", "K99", "R00"]


async def search(query: str, limit: int = 10) -> list[dict]:
    payload = {
        "criteria": {
            "project_terms": query,
            "activity_codes": _TRAINEE_ACTIVITY_CODES,
        },
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
        activity = proj.get("activity_code", "")
        results.append(
            {
                "title": proj.get("project_title", ""),
                "funder": f"NIH ({activity})" if activity else "NIH",
                "organization": proj.get("organization", {}).get("org_name", ""),
                "pi": pi_name,
                "fiscal_year": str(proj.get("fiscal_year", "")),
                "amount": f"${award:,}" if award else "",
                "url": _DETAIL.format(id=proj.get("appl_id", "")),
                "summary": (proj.get("abstract_text") or "")[:300],
                "source": "NIH Reporter",
            }
        )
    return results
