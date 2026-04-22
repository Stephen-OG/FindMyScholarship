"""
FindMyScholarship MCP Server

Exposes real-time academic funding data from three public APIs:
  - Grants.gov       (US federal scholarships & research grants)
  - UKRI GtR         (UK research council funded projects)
  - NIH Reporter     (NIH-funded biomedical research grants)

Run with:
    python -m mcp_server.server

Configure in Claude Desktop (~/.claude/claude_desktop_config.json):
    {
      "mcpServers": {
        "findmyscholarship": {
          "command": "python",
          "args": ["-m", "mcp_server.server"],
          "cwd": "/path/to/FindMySchorlarship"
        }
      }
    }
"""

import asyncio

from mcp.server.fastmcp import FastMCP

from mcp_server.sources import grants_gov, nih, ukri

mcp = FastMCP(
    "FindMyScholarship",
    instructions=(
        "Provides real-time academic funding opportunities — scholarships, bursaries, "
        "studentships, fellowships, and research grants — for undergraduate, postgraduate, "
        "doctoral, and postdoctoral students. Data is fetched live from Grants.gov (US), "
        "UKRI Gateway to Research (UK), and NIH Reporter (US)."
    ),
)

# ── level keyword enrichment ──────────────────────────────────────────────────

_LEVEL_TERMS: dict[str, str] = {
    "undergraduate": "undergraduate scholarship bursary",
    "postgraduate": "postgraduate masters scholarship bursary studentship",
    "doctoral": "PhD studentship doctoral fellowship",
    "postdoctoral": "postdoctoral fellowship research grant early career",
    "any": "scholarship fellowship studentship bursary",
}

_GRANT_LEVEL_TERMS: dict[str, str] = {
    "postgraduate": "research grant studentship masters",
    "doctoral": "PhD studentship doctoral research grant",
    "postdoctoral": "postdoctoral fellowship research grant early career",
    "any": "research grant fellowship studentship",
}


# ── shared formatter ──────────────────────────────────────────────────────────

def _format_results(label: str, results: list[dict] | Exception) -> str:
    if isinstance(results, Exception):
        return f"## {label}\n_Could not fetch results: {results}_\n"
    if not results:
        return f"## {label}\nNo results found.\n"

    lines = [f"## {label} ({len(results)} results)"]
    for i, r in enumerate(results, 1):
        block = [f"### {i}. {r.get('title') or 'Untitled'}"]
        for field, heading in [
            ("funder", "Funder"),
            ("organization", "Organization"),
            ("pi", "Principal Investigator"),
            ("fiscal_year", "Fiscal Year"),
            ("deadline", "Deadline"),
            ("start", "Start"),
            ("end", "End"),
            ("amount", "Award"),
        ]:
            if r.get(field):
                block.append(f"**{heading}:** {r[field]}")
        if r.get("summary"):
            block.append(f"**Summary:** {r['summary']}")
        if r.get("url"):
            block.append(f"**Link:** {r['url']}")
        lines.append("\n".join(block))

    return "\n\n".join(lines)


# ── tools ─────────────────────────────────────────────────────────────────────

@mcp.tool()
async def search_scholarships(
    query: str,
    level: str = "any",
    country: str = "any",
    limit: int = 10,
) -> str:
    """
    Search for academic scholarships, bursaries, and studentships.

    Args:
        query: Topic, field of study, or institution name
               (e.g. "machine learning", "University of Edinburgh", "STEM women")
        level: Degree level — "undergraduate", "postgraduate", "doctoral",
               "postdoctoral", or "any"
        country: Region filter — "us", "uk", or "any"
        limit: Max results per source (1-25, default 10)
    """
    enriched = f"{query} {_LEVEL_TERMS.get(level, _LEVEL_TERMS['any'])}"
    limit = max(1, min(limit, 25))

    tasks: list = []
    labels: list[str] = []

    if country in ("any", "us"):
        tasks.append(grants_gov.search(enriched, rows=limit))
        labels.append("Grants.gov (US Federal)")
    if country in ("any", "uk"):
        tasks.append(ukri.search(enriched, page_size=limit))
        labels.append("UKRI Gateway to Research (UK)")

    if not tasks:
        return "Unsupported country filter. Use 'us', 'uk', or 'any'."

    raw = await asyncio.gather(*tasks, return_exceptions=True)
    sections = [_format_results(lbl, res) for lbl, res in zip(labels, raw)]
    return "\n\n---\n\n".join(sections)


@mcp.tool()
async def search_research_grants(
    subject: str,
    level: str = "any",
    country: str = "any",
    limit: int = 10,
) -> str:
    """
    Search for research grants and fellowships for postgraduate, doctoral,
    and postdoctoral researchers.

    Args:
        subject: Research area or topic (e.g. "climate change", "quantum computing",
                 "cancer immunotherapy")
        level: "postgraduate", "doctoral", "postdoctoral", or "any"
        country: "us", "uk", or "any"
        limit: Max results per source (1-25, default 10)
    """
    enriched = f"{subject} {_GRANT_LEVEL_TERMS.get(level, _GRANT_LEVEL_TERMS['any'])}"
    limit = max(1, min(limit, 25))

    tasks: list = []
    labels: list[str] = []

    if country in ("any", "us"):
        tasks.append(grants_gov.search(enriched, rows=limit))
        labels.append("Grants.gov (US Federal)")
        tasks.append(nih.search(enriched, limit=limit))
        labels.append("NIH Reporter (US Biomedical)")
    if country in ("any", "uk"):
        tasks.append(ukri.search(enriched, page_size=limit))
        labels.append("UKRI Gateway to Research (UK)")

    if not tasks:
        return "Unsupported country filter. Use 'us', 'uk', or 'any'."

    raw = await asyncio.gather(*tasks, return_exceptions=True)
    sections = [_format_results(lbl, res) for lbl, res in zip(labels, raw)]
    return "\n\n---\n\n".join(sections)


@mcp.tool()
async def search_all_funding(
    query: str,
    level: str = "any",
    country: str = "any",
    limit: int = 8,
) -> str:
    """
    Broad funding search across scholarships AND research grants simultaneously.
    Best for open-ended queries like "AI funding UK PhD".

    Args:
        query: Free-text query (field, level, institution, or topic)
        level: "undergraduate", "postgraduate", "doctoral", "postdoctoral", or "any"
        country: "us", "uk", or "any"
        limit: Max results per source (1-20, default 8)
    """
    level_hint = _LEVEL_TERMS.get(level, _LEVEL_TERMS["any"])
    enriched = f"{query} {level_hint}"
    limit = max(1, min(limit, 20))

    tasks: list = []
    labels: list[str] = []

    if country in ("any", "us"):
        tasks.append(grants_gov.search(enriched, rows=limit))
        labels.append("Grants.gov (US Federal)")
        tasks.append(nih.search(enriched, limit=limit))
        labels.append("NIH Reporter (US Biomedical)")
    if country in ("any", "uk"):
        tasks.append(ukri.search(enriched, page_size=limit))
        labels.append("UKRI Gateway to Research (UK)")

    if not tasks:
        return "Unsupported country filter. Use 'us', 'uk', or 'any'."

    raw = await asyncio.gather(*tasks, return_exceptions=True)
    sections = [_format_results(lbl, res) for lbl, res in zip(labels, raw)]
    return "\n\n---\n\n".join(sections)


@mcp.tool()
async def list_funding_sources() -> str:
    """
    List all data sources this server queries, their geographic coverage,
    and what types of funding they cover.
    """
    return """\
## FindMyScholarship MCP — Live Data Sources

| Source | Region | Coverage |
|--------|--------|----------|
| [Grants.gov](https://www.grants.gov) | USA | All US federal funding: scholarships, fellowships, research grants across all degree levels |
| [UKRI Gateway to Research](https://gtr.ukri.org) | UK | UKRI-funded projects: doctoral studentships, postdoctoral fellowships, early-career grants |
| [NIH Reporter](https://reporter.nih.gov) | USA | NIH-funded biomedical & health research: PhD, postdoc, and faculty-level grants |

**All data is fetched live** — results reflect currently open and forecasted opportunities.

### Which tool to use
- `search_scholarships` — student-facing awards (scholarships, bursaries, studentships)
- `search_research_grants` — researcher-facing awards (grants, fellowships, PI funding)
- `search_all_funding` — broad open-ended search across both categories
"""


if __name__ == "__main__":
    mcp.run()
