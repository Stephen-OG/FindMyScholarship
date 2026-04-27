"""UKRI Gateway to Research API — UK research council funded projects."""

import logging

import httpx

log = logging.getLogger(__name__)

_BASE = "https://gtr.ukri.org/gtr/api/projects"
_DETAIL = "https://gtr.ukri.org/projects?ref={id}"


async def search(query: str, page_size: int = 10) -> list[dict]:
    # Minimum page size enforced by the API is 10
    params = {"q": query[:200], "s": max(page_size, 10), "p": 1}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(_BASE, params=params, headers={"Accept": "application/json"})
        resp.raise_for_status()
        data = resp.json()
        log.debug("UKRI raw response: %s", data)

    results = []
    for project in data.get("project") or []:
        # Funder: top-level in current API schema (fund object removed)
        funder = project.get("leadFunder") or "UKRI"

        # Dates: top-level (None for many studentships)
        start = project.get("start") or ""
        end = project.get("end") or ""

        # Cost: aggregated from participant values (absent for most studentships)
        participants = (project.get("participantValues") or {}).get("participant") or []
        total_cost = sum(p.get("projectCost") or 0 for p in participants)
        amount = f"£{total_cost:,.0f}" if total_cost else ""

        # URL: prefer RCUK identifier over UUID — the GtR website uses RCUK ref
        identifiers = (project.get("identifiers") or {}).get("identifier") or []
        rcuk_id = next((i["value"] for i in identifiers if i.get("type") == "RCUK"), None)
        project_ref = rcuk_id or project.get("id", "")
        url = _DETAIL.format(id=project_ref) if project_ref else ""

        results.append(
            {
                "title": project.get("title", ""),
                "funder": funder,
                "start": start,
                "end": end,
                "amount": amount,
                "url": url,
                "summary": (project.get("abstractText") or "")[:300],
                "source": "UKRI Gateway to Research",
            }
        )

    log.info("UKRI search(%r) → %d results", query, len(results))
    return results
