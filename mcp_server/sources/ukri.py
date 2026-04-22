"""UKRI Gateway to Research API — UK research council funded projects."""

import httpx

_BASE = "https://gtr.ukri.org/gtr/api/projects"
_DETAIL = "https://gtr.ukri.org/projects?ref={id}"


async def search(query: str, page_size: int = 10) -> list[dict]:
    # UKRI GtR only accepts q, s, p — sort params cause 400
    params = {"q": query[:200], "s": page_size, "p": 1}
    headers = {"Accept": "application/vnd.rcuk.gtr.json-v7"}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(_BASE, params=params, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    results = []
    for project in data.get("project", []):
        fund = project.get("fund", {})
        amount_pence = fund.get("valuePounds", {}).get("amount")
        results.append(
            {
                "title": project.get("title", ""),
                "funder": fund.get("funder", {}).get("name", "UKRI"),
                "start": fund.get("start", ""),
                "end": fund.get("end", ""),
                "amount": f"£{amount_pence:,}" if amount_pence else "",
                "url": _DETAIL.format(id=project.get("id", "")),
                "summary": (project.get("abstractText") or "")[:300],
                "source": "UKRI Gateway to Research",
            }
        )
    return results
