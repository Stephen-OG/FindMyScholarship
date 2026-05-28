# 🎓 FindMyScholarship AI

An AI agent that helps students and researchers find scholarships, fellowships, studentships, and research grants — in real time, from authoritative sources.

Instead of a static database, the agent combines **live national funding databases** with **on-demand university website crawling**, then presents results conversationally through a chat interface.

---

## How it works

A single natural-language query triggers a two-track search:

```
User Query
    │
    ├── National DB track (fast, ~2s)
    │     MCP server queries four live databases in parallel:
    │       • Grants.gov        (US federal scholarships & research grants)
    │       • UKRI Gateway to Research  (UK research council funding)
    │       • NIH Reporter      (NIH-funded biomedical projects)
    │       • jobs.ac.uk        (UK & international funded PhD studentships)
    │
    └── University crawl track
          Domain discovery → web crawl → LLM analysis
          Extracts: name, amount, deadline, eligibility, degree level
```

Results from both tracks are combined and streamed back as a chat response. Follow-up questions (filtering, comparisons) are handled without re-crawling.

---

## Features

- **Natural language queries** — e.g. *"fully funded PhD in machine learning UK"*, *"postdoc fellowships computational biology USA"*
- **Live national databases** — Grants.gov, UKRI, NIH Reporter, jobs.ac.uk searched in real time
- **University web crawling** — automatically discovers and crawls official funding pages
- **LLM-powered extraction** — structured fields (amount, deadline, eligibility, degree level) pulled from raw page content
- **Conversational follow-ups** — ask clarifying questions without re-triggering a full search
- **Streaming UI** — progress messages appear as the agent works

---

## Tech stack

| Layer | Technology |
|---|---|
| UI | Gradio (streaming chat) |
| Agent framework | OpenAI Agents SDK |
| National DB interface | MCP (Model Context Protocol) server |
| Web crawling | aiohttp + BeautifulSoup + Playwright |
| LLM | GPT-4o-mini (routing, extraction, analysis) |
| Cache | SQLite (aiosqlite) |
| Runtime | Python 3.12, Docker |

---

## Getting started

### Prerequisites

- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- `OPENAI_API_KEY` — required
- `SERPAPI_API_KEY` — optional (fallback domain lookup if DuckDuckGo fails)

### Install

```bash
git clone https://github.com/ogunderoStephen/FindMySchorlarship.git
cd FindMySchorlarship
uv sync
```

### Configure

```bash
cp .env.example .env   # then fill in your keys
# or just:
echo "OPENAI_API_KEY=sk-..." > .env
```

### Run

```bash
uv run python app.py
```

Open the URL printed in the terminal (default: `http://localhost:7860`).

---

## Deployment (Hugging Face Spaces)

This project ships a `Dockerfile` for Hugging Face Docker Spaces.

1. Create a new Space → choose **Docker** as the SDK
2. Push this repository to the Space
3. In **Space → Settings → Variables and secrets**, add:
   - `OPENAI_API_KEY`
   - `SERPAPI_API_KEY` (optional)
4. Restart the Space

---

## Project layout

```
app.py                          # Gradio entry point
mcp_server/
  server.py                     # MCP server (4 live funding sources)
  sources/
    grants_gov.py               # Grants.gov API
    ukri.py                     # UKRI Gateway to Research API
    nih.py                      # NIH Reporter API
    jobs_ac_uk.py               # jobs.ac.uk PhD listings
    opportunity_desk.py         # OpportunityDesk aggregator
scholarship_agents/
  schorlarship_agent.py         # Main agent (routing, orchestration, streaming)
  explorer_agent.py             # Follow-up / results explorer agent
  school_domain_agent.py        # University domain discovery agent
utils/
  crawl/                        # Async web crawler (engine, scorer, cache)
  analyzer.py                   # LLM funding page analysis
  keyword_extractor.py          # Query → structured keywords
  university_db.py              # Curated university domain database
  find_domain.py                # Tiered domain lookup (DB → DDG → SerpAPI)
eval/
  harness.py                    # Evaluation harness with metrics
  golden_dataset.py             # Golden test cases (university + MCP paths)
```

---

## Engineering challenges

Building this surfaced several non-obvious problems worth documenting.

**1. Crawler blocked in production**
The initial aiohttp-only crawler worked locally but was blocked by Cloudflare and similar bot-detection on university sites in production. The fix was integrating Playwright for JavaScript-rendered pages and sites that require a real browser fingerprint. The crawler now uses Playwright selectively — aiohttp for straightforward pages, Playwright for those that require it — keeping costs and latency reasonable.

> **What's next here:** Playwright can also be used actively, not just passively — following seeded links, interacting with forms, and navigating paginated funding listings before handing the resulting pages to the analyzer. This would unlock funding databases that require interaction to surface results.

**2. Context window overflow after adding MCP**
Adding the MCP server (4 national databases) increased the volume of raw text the agent was accumulating before analysis. Running all university crawls first, then analyzing, filled the context window and caused the agent to fail or truncate results.

The solution was a **crawl-and-analyze-per-batch** pattern: after crawling a batch of 2 universities, the agent immediately calls `analyze_crawler_results` on that batch before moving to the next one. The full page text is stripped from the crawler's output before it reaches the agent — only lean metadata (URL, title, relevance score) is returned — while the full text is preserved in a local cache for the analyzer to read directly. This keeps the agent context lean regardless of how many universities are searched.

**3. Follow-up questions re-triggering full crawls**
Without routing logic, asking *"show me only the fully funded ones"* after a search would launch a new crawl instead of filtering the existing results. The fix was a lightweight LLM router that classifies each message as `SEARCH`, `FOLLOWUP`, or `GENERAL` before deciding which agent to invoke. Follow-up questions are handed off to a read-only `explorer_agent` that has no crawl tools — it can only reason over what's already in the conversation.

---

## Limitations

- University crawl results depend on page structure and bot-access policies
- Grants.gov and NIH search against a broad federal corpus — results for academic queries may include non-academic programs
- API usage incurs costs (OpenAI, optionally SerpAPI)
- Results are for research assistance; verify deadlines and eligibility directly with funders

---

**Made for students and researchers who shouldn't have to spend hours hunting for funding.**
