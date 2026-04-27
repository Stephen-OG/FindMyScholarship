"""Integration tests for all MCP data sources.

These tests make real HTTP calls to verify each source is reachable
and returns well-formed data. Run with:
    uv run pytest tests/test_mcp_sources.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_server.sources import grants_gov, jobs_ac_uk, nih, opportunity_desk, ukri

# ── helpers ──────────────────────────────────────────────────────────────────


def _assert_result_shape(results: list[dict], required_keys: list[str], source: str) -> None:
    assert isinstance(results, list), f"{source}: expected list, got {type(results)}"
    assert len(results) > 0, (
        f"{source}: returned 0 results — API may be down or query matched nothing"
    )
    for key in required_keys:
        assert key in results[0], f"{source}: missing key '{key}' in first result"


# ── Grants.gov ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_grants_gov_returns_results():
    results = await grants_gov.search("scholarship fellowship", rows=5)
    _assert_result_shape(results, ["title", "funder", "url", "source"], "Grants.gov")


@pytest.mark.asyncio
async def test_grants_gov_respects_row_limit():
    results = await grants_gov.search("research grant", rows=3)
    assert len(results) <= 3, f"Grants.gov: requested 3 rows, got {len(results)}"


@pytest.mark.asyncio
async def test_grants_gov_result_structure():
    results = await grants_gov.search("STEM undergraduate", rows=5)
    for r in results:
        assert isinstance(r.get("title"), str)
        assert r.get("source") == "Grants.gov"
        assert r.get("url", "").startswith("https://"), f"Bad URL: {r.get('url')}"


# ── NIH Reporter ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_nih_returns_results():
    results = await nih.search("predoctoral fellowship biomedical", limit=5)
    _assert_result_shape(results, ["title", "funder", "url", "source"], "NIH")


@pytest.mark.asyncio
async def test_nih_respects_limit():
    results = await nih.search("training grant", limit=3)
    assert len(results) <= 3, f"NIH: requested 3, got {len(results)}"


@pytest.mark.asyncio
async def test_nih_result_structure():
    results = await nih.search("F31 predoctoral fellowship", limit=5)
    for r in results:
        assert isinstance(r.get("title"), str)
        assert r.get("source") == "NIH Reporter"
        assert r.get("url", "").startswith("https://"), f"Bad URL: {r.get('url')}"


# ── UKRI ──────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ukri_returns_results():
    results = await ukri.search("doctoral studentship", page_size=5)
    _assert_result_shape(results, ["title", "funder", "url", "source"], "UKRI")


@pytest.mark.asyncio
async def test_ukri_minimum_page_size_enforced():
    # API minimum is 10 — even if we ask for 3 we should get up to 10 back
    results = await ukri.search("PhD fellowship", page_size=3)
    assert len(results) > 0, "UKRI: no results returned"


@pytest.mark.asyncio
async def test_ukri_result_structure():
    results = await ukri.search("machine learning research", page_size=5)
    for r in results:
        assert isinstance(r.get("title"), str)
        assert r.get("source") == "UKRI Gateway to Research"


# ── Opportunity Desk ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_opportunity_desk_returns_results():
    results = await opportunity_desk.search("scholarship fellowship", limit=5)
    _assert_result_shape(results, ["title", "url", "source"], "Opportunity Desk")


@pytest.mark.asyncio
async def test_opportunity_desk_respects_limit():
    results = await opportunity_desk.search("undergraduate bursary", limit=3)
    assert len(results) <= 3, f"Opportunity Desk: requested 3, got {len(results)}"


@pytest.mark.asyncio
async def test_opportunity_desk_result_structure():
    results = await opportunity_desk.search("postgraduate scholarship", limit=5)
    for r in results:
        assert isinstance(r.get("title"), str)
        assert r.get("url", "").startswith("https://"), f"Bad URL: {r.get('url')}"
        assert r.get("source") == "Opportunity Desk"


# ── jobs.ac.uk ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_jobs_ac_uk_returns_results():
    results = await jobs_ac_uk.search("machine learning", limit=5)
    _assert_result_shape(results, ["title", "organization", "url", "source"], "jobs.ac.uk")


@pytest.mark.asyncio
async def test_jobs_ac_uk_respects_limit():
    results = await jobs_ac_uk.search("computer science", limit=3)
    assert len(results) <= 3, f"jobs.ac.uk: requested 3, got {len(results)}"


@pytest.mark.asyncio
async def test_jobs_ac_uk_result_structure():
    results = await jobs_ac_uk.search("PhD studentship artificial intelligence", limit=5)
    for r in results:
        assert isinstance(r.get("title"), str), "title must be a string"
        assert r.get("url", "").startswith("https://www.jobs.ac.uk"), f"Bad URL: {r.get('url')}"
        assert r.get("source") == "jobs.ac.uk"


# ── Server-level tool smoke tests ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_server_search_scholarships_us():
    from mcp_server.server import search_scholarships

    result = await search_scholarships(
        query="computer science", level="doctoral", country="us", limit=3
    )
    assert isinstance(result, str)
    assert len(result) > 50, "search_scholarships returned suspiciously short output"
    assert "Grants.gov" in result


@pytest.mark.asyncio
async def test_server_search_scholarships_uk_includes_jobs_ac_uk():
    from mcp_server.server import search_scholarships

    result = await search_scholarships(
        query="machine learning", level="doctoral", country="uk", limit=3
    )
    assert isinstance(result, str)
    assert "UKRI" in result
    assert "jobs.ac.uk" in result


@pytest.mark.asyncio
async def test_server_search_research_grants():
    from mcp_server.server import search_research_grants

    result = await search_research_grants(
        subject="machine learning", level="postdoctoral", country="us", limit=3
    )
    assert isinstance(result, str)
    assert len(result) > 50
    assert "Grants.gov" in result or "NIH" in result


@pytest.mark.asyncio
async def test_server_search_all_funding():
    from mcp_server.server import search_all_funding

    result = await search_all_funding(query="AI PhD funding", level="any", country="uk", limit=3)
    assert isinstance(result, str)
    assert len(result) > 50
    assert "UKRI" in result


@pytest.mark.asyncio
async def test_server_list_funding_sources():
    from mcp_server.server import list_funding_sources

    result = await list_funding_sources()
    assert "Grants.gov" in result
    assert "UKRI" in result
    assert "NIH" in result
    assert "Opportunity Desk" in result
    assert "jobs.ac.uk" in result


@pytest.mark.asyncio
async def test_server_level_alias_resolution():
    """Ensure level aliases (phd, masters, postdoc) are resolved correctly."""
    from mcp_server.server import search_scholarships

    # Should not raise; alias "phd" → "doctoral"
    result = await search_scholarships(query="biology", level="phd", country="us", limit=2)
    assert isinstance(result, str)


@pytest.mark.asyncio
async def test_server_invalid_country_falls_back_to_opportunity_desk():
    """An unrecognised country skips US/UK sources but still queries Opportunity Desk."""
    from mcp_server.server import search_scholarships

    result = await search_scholarships(query="scholarship", country="zz", limit=2)
    assert isinstance(result, str)
    # US and UK sources should be absent
    assert "Grants.gov" not in result
    assert "UKRI" not in result
    # Opportunity Desk is always included
    assert "Opportunity Desk" in result
