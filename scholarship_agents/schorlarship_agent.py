import asyncio
from typing import Any, AsyncIterator, Optional

from agents import Agent, RunHooks, Runner, handoff
from openai import AsyncOpenAI

from scholarship_agents.explorer_agent import explorer_agent
from scholarship_agents.school_domain_agent import search_agent
from utils.analyzer import analyze_crawler_results
from utils.crawl import crawl_universities_formatted
from utils.keyword_extractor import extract_query_keywords
from utils.logger import logger

# Deferred so it's created after load_dotenv() runs in app.py.
_openai_client: AsyncOpenAI | None = None


def _get_openai_client() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI()
    return _openai_client


logger.info("Starting scholarship agent")

search_agent_tool = search_agent.as_tool(
    tool_name="university_domain_search",
    tool_description="Find university domains for given schools or research topics. Call ONCE per query to get all relevant universities. Returns list of universities with their official domains.",
)

tools = [search_agent_tool, crawl_universities_formatted, analyze_crawler_results]

system_prompt = """
You are FindMyScholarship AI — you help students find university funding opportunities.

WORKFLOW (run each step once, in order):
1. DOMAINS  — call university_domain_search to get official university URLs.
              If the query names no universities, search up to 5. If the query is
              too vague, ask the user to narrow it before searching.
2. CRAWL    — call crawl_universities_formatted in batches of up to 4 universities.
              Always pass: user_query AND extracted_keywords (from [SYSTEM CONTEXT]).
3. ANALYZE  — call analyze_crawler_results once with all crawled universities.
              Always pass: user_query AND extracted_keywords (from [SYSTEM CONTEXT]).
4. PRESENT  — show results grouped by university, then hand off to results_explorer.

KEYWORDS: The user message contains a [SYSTEM CONTEXT] block with extracted_keywords.
You MUST forward that exact list to both crawl and analyze tool calls.

OUTPUT RULES:
- Omit any field (deadline, amount, eligibility) not found — never write "Not specified"
- Missing deadline → "→ Check the funding page for current deadlines"
- Missing amount   → "→ Contact the department for funding details"
- Every opportunity must end with a direct link or clear next step
- Zero results → say so plainly and give 2-3 concrete next steps
"""

scholarship_agent = Agent(
    name="Scholarship Researcher",
    instructions=system_prompt,
    tools=tools,
    handoffs=[handoff(explorer_agent)],
    model="gpt-4o-mini",
)

# Per-tool call limits enforced programmatically (not just via prompt).
# university_domain_search: 2 — allows one retry if the first result is thin.
# crawl_universities_formatted: 2 — supports batching across university groups.
# analyze_crawler_results: 1 — analysis should never be repeated.
_TOOL_MAX_CALLS: dict[str, int] = {
    "university_domain_search": 2,
    "crawl_universities_formatted": 2,
    "analyze_crawler_results": 1,
}


# Human-readable progress labels shown in the Gradio chat bubble while the
# agent is running. Keys match the tool names registered above.
_TOOL_PROGRESS: dict[str, str] = {
    "university_domain_search": "Searching for university domains...",
    "crawl_universities_formatted": "Crawling university websites for funding pages...",
    "analyze_crawler_results": "Analysing funding pages with AI...",
}
_TOOL_DONE: dict[str, str] = {
    "university_domain_search": "University domains found.",
    "crawl_universities_formatted": "Crawl complete.",
    "analyze_crawler_results": "Analysis complete.",
}


class ToolCallGuard(RunHooks):
    """
    Enforces per-tool call limits AND streams progress messages into an
    asyncio.Queue so the Gradio UI can display live status updates.

    Pass a queue to enable streaming; omit it for non-streaming use.
    """

    def __init__(self, progress_queue: Optional[asyncio.Queue] = None) -> None:
        self._counts: dict[str, int] = {}
        self._queue = progress_queue

    async def _emit(self, message: str) -> None:
        if self._queue is not None:
            await self._queue.put(message)

    async def on_tool_start(self, context: Any, agent: Any, tool: Any) -> None:
        name = getattr(tool, "name", str(tool))
        self._counts[name] = self._counts.get(name, 0) + 1
        limit = _TOOL_MAX_CALLS.get(name)
        if limit is not None and self._counts[name] > limit:
            logger.warning(
                "ToolCallGuard: '%s' called %d times (max %d) — blocking call",
                name,
                self._counts[name],
                limit,
            )
            # Mark this call as blocked so on_tool_end knows to skip the done label
            self._blocked_calls: set = getattr(self, "_blocked_calls", set())
            self._blocked_calls.add(name)
            raise RuntimeError(
                f"[LIMIT] '{name}' has already been called the maximum number of times. "
                "Use the results you already have and proceed to the next step."
            )
        progress = _TOOL_PROGRESS.get(name)
        if progress:
            await self._emit(f"*{progress}*")

    async def on_tool_end(self, context: Any, agent: Any, tool: Any, result: str) -> None:
        name = getattr(tool, "name", str(tool))
        done = _TOOL_DONE.get(name)
        if done:
            await self._emit(f"*{done}*")


def _build_messages(
    message: str,
    history,
    *,
    use_explorer: bool = False,
    keywords: list[str] | None = None,
) -> list:
    """
    Convert Gradio history + current message into Responses API input items.

    If `keywords` are provided (pre-extracted before agent run), they are
    appended to the user message as an explicit context block.  The agent
    reads this and MUST pass extracted_keywords to both crawl and analyze
    tool calls — eliminating redundant in-tool extraction.
    """
    messages = []
    for turn in history:
        if isinstance(turn, (list, tuple)) and len(turn) >= 2:
            user_msg, ai_msg = turn[0], turn[1]
        elif isinstance(turn, dict):
            role = turn.get("role")
            content = (
                turn.get("content")
                or turn.get("message")
                or turn.get("user")
                or turn.get("assistant")
            )
            user_msg = content if role == "user" else None
            ai_msg = content if role == "assistant" else None
        else:
            continue
        if user_msg:
            messages.append(
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": str(user_msg)}],
                }
            )
        if ai_msg:
            messages.append(
                {
                    "role": "assistant",
                    "content": [{"type": "output_text", "text": str(ai_msg)}],
                }
            )

    # Append pre-extracted keywords as a mandatory context block so the agent
    # never needs to call extract_query_keywords itself.
    if keywords and not use_explorer:
        kw_block = (
            f"\n\n[SYSTEM CONTEXT — DO NOT SHOW TO USER]\n"
            f"extracted_keywords: {keywords}\n"
            f"IMPORTANT: Pass this exact list as the `extracted_keywords` parameter "
            f"to BOTH crawl_universities_formatted AND analyze_crawler_results."
        )
        messages.append(
            {
                "role": "user",
                "content": [{"type": "input_text", "text": message + kw_block}],
            }
        )
    else:
        messages.append({"role": "user", "content": [{"type": "input_text", "text": message}]})
    return messages


_ROUTE_SYSTEM = """\
You are a router for a scholarship-search assistant.
Classify the user's message into exactly one of three labels — no punctuation, no explanation.

SEARCH   → user wants to find/look up scholarships, grants, fellowships, or funding at
           a university or programme (triggers a live crawl).
           Examples: "PhD funding in AI at Oxford", "masters scholarships in Canada",
           "find funding at University of Exeter", "apply for Chevening".

FOLLOWUP → user is asking about, filtering, or comparing results already shown in this
           conversation. Only valid when prior_results=true.
           Examples: "show me only fully funded ones", "what about computer science?",
           "compare these two", "tell me more about the first one".

GENERAL  → anything else: factual questions, advice, small talk, topic overviews.
           Examples: "list top universities in Sweden", "top research topics with good funding",
           "what GPA do I need?", "how do I write a personal statement?".

When in doubt between FOLLOWUP and SEARCH, prefer SEARCH.
When in doubt between SEARCH and GENERAL, prefer GENERAL.\
"""


async def _classify_route(message: str, has_prior_results: bool) -> str:
    """
    Return one of 'SEARCH' | 'FOLLOWUP' | 'GENERAL'.

    A single cheap LLM call replaces the previous three-function chain
    (_classify_intent + _is_new_search + _is_followup). The has_prior_results
    flag is passed as context so FOLLOWUP is only ever returned when there is
    actually something in history to follow up on.

    Falls back to 'SEARCH' on error so we never silently drop a real search.
    """
    context = f"prior_results={str(has_prior_results).lower()}\n\nUser: {message}"
    try:
        resp = await _get_openai_client().chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _ROUTE_SYSTEM},
                {"role": "user", "content": context},
            ],
            max_tokens=5,
            temperature=0,
        )
        label = resp.choices[0].message.content.strip().upper()
        if label not in ("SEARCH", "FOLLOWUP", "GENERAL"):
            logger.warning("Unexpected route label %r — defaulting to SEARCH", label)
            return "SEARCH"
        logger.info("Route: %s (prior_results=%s) — %r", label, has_prior_results, message[:80])
        return label
    except Exception as exc:
        logger.warning("Route classification failed (%s) — defaulting to SEARCH", exc)
        return "SEARCH"


def _has_prior_results(history) -> bool:
    """
    True when history contains a completed funding search response.

    Uses two signals on each assistant message to filter out short errors,
    status strings, and clarifying questions:
    1. Length > 400 chars
    2. At least 3 distinct funding-domain terms present
    """
    _FUNDING_TERMS = frozenset(
        {
            "scholarship",
            "studentship",
            "fellowship",
            "bursary",
            "grant",
            "stipend",
            "tuition",
            "funded",
            "funding",
            "phd",
            "doctoral",
            "masters",
            "postdoctoral",
            "assistantship",
        }
    )
    for turn in history:
        ai_msg = None
        if isinstance(turn, (list, tuple)) and len(turn) >= 2:
            ai_msg = turn[1]
        elif isinstance(turn, dict) and turn.get("role") == "assistant":
            ai_msg = turn.get("content", "")
        if not ai_msg or len(str(ai_msg)) < 400:
            continue
        if sum(1 for t in _FUNDING_TERMS if t in str(ai_msg).lower()) >= 3:
            return True
    return False


async def _answer_general_query(message: str, history) -> AsyncIterator[str]:
    """
    Handle non-scholarship queries with a direct LLM call.

    Yields the answer incrementally (streaming) without triggering the
    agent pipeline (no domain lookup, no crawl, no analysis).
    """
    system_msg = (
        "You are FindMyScholarship AI, a helpful assistant for students. "
        "Answer the user's question clearly and concisely. "
        "If the question is about universities or education, provide accurate information. "
        "If the user wants to search for scholarships or funding, let them know they can "
        "describe what they're looking for and you'll search for opportunities."
    )
    messages = [{"role": "system", "content": system_msg}]
    for turn in history:
        if isinstance(turn, (list, tuple)) and len(turn) >= 2:
            if turn[0]:
                messages.append({"role": "user", "content": str(turn[0])})
            if turn[1]:
                messages.append({"role": "assistant", "content": str(turn[1])})
        elif isinstance(turn, dict):
            role = turn.get("role")
            content = turn.get("content") or ""
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": str(content)})
    messages.append({"role": "user", "content": message})

    accumulated = ""
    stream = await _get_openai_client().chat.completions.create(
        model="gpt-4o-mini",
        messages=messages,
        stream=True,
        temperature=0.5,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        if delta:
            accumulated += delta
            yield accumulated


async def chat_stream(message: str, history) -> AsyncIterator[str]:
    """
    Streaming version of chat().

    Yields incremental status strings while the agent runs tools, then
    yields the final answer once the agent finishes.  Each yielded value
    is the *full current* assistant bubble text (Gradio streaming convention).

    Routes follow-up questions directly to explorer_agent to avoid re-crawling.

    Pre-extracts keywords before the agent runs and injects them into the
    context message so the agent always passes them to crawler and analyzer —
    guaranteeing a single LLM extraction call per query regardless of whether
    the model remembers to forward the parameter.
    """
    route = await _classify_route(message, _has_prior_results(history))

    if route == "GENERAL":
        async for partial in _answer_general_query(message, history):
            yield partial
        return

    is_followup = route == "FOLLOWUP"
    active_agent = explorer_agent if is_followup else scholarship_agent

    # Pre-extract keywords once for SEARCH so crawler + analyzer reuse them.
    # FOLLOWUP skips this — explorer has no tools.
    extracted_keywords: list[str] = []
    if not is_followup:
        try:
            kw = await extract_query_keywords(message)
            extracted_keywords = kw.all_keywords
            logger.info("Pre-extracted keywords: %s", extracted_keywords)
        except Exception as exc:
            logger.warning("Keyword pre-extraction failed, agent will extract inline: %s", exc)

    messages = _build_messages(
        message, history, use_explorer=is_followup, keywords=extracted_keywords
    )
    progress_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
    guard = ToolCallGuard(progress_queue=progress_queue) if not is_followup else None

    _SENTINEL = object()
    accumulated_status: list[str] = []

    async def _run_agent():
        try:
            result = await asyncio.wait_for(
                Runner.run(
                    active_agent,
                    messages,
                    max_turns=8 if not is_followup else 3,
                    hooks=guard,
                ),
                timeout=300,
            )
            await progress_queue.put(result.final_output)
        except asyncio.TimeoutError:
            logger.error("Scholarship agent timed out")
            await progress_queue.put("The search timed out. Please try a narrower query.")
        except RuntimeError as exc:
            msg = str(exc)
            if "[LIMIT]" in msg:
                # A tool was called more times than its guard allows.
                # The agent already gathered results; ask it to wrap up instead of crashing.
                logger.warning("ToolCallGuard fired during streaming run: %s", msg)
                await progress_queue.put(
                    "The agent reached its tool-call budget. "
                    "Please retry — if this persists, try a narrower query."
                )
            else:
                logger.error("Scholarship agent runtime error: %s", exc)
                await progress_queue.put("The search hit an internal error. Please retry.")
        except Exception as exc:
            logger.error("Scholarship agent failed: %s", exc)
            await progress_queue.put("The search hit an internal error. Please retry.")
        finally:
            await progress_queue.put(_SENTINEL)  # type: ignore[arg-type]

    agent_task = asyncio.create_task(_run_agent())

    while True:
        item = await progress_queue.get()
        if item is _SENTINEL:
            break
        # Status messages (italics) are shown as a growing progress log
        # until the final answer arrives (which replaces all of it).
        if item and item.startswith("*") and item.endswith("*"):
            accumulated_status.append(item)
            yield "\n\n".join(accumulated_status)
        else:
            # Final answer — replace status lines with the real response
            yield item

    await agent_task


async def chat(message: str, history) -> str:
    """
    Non-streaming wrapper kept for backward compatibility.
    Returns the complete final answer string.
    """
    messages = _build_messages(message, history)
    try:
        response = await asyncio.wait_for(
            Runner.run(scholarship_agent, messages, max_turns=8, hooks=ToolCallGuard()),
            timeout=300,
        )
        return response.final_output
    except asyncio.TimeoutError:
        logger.error("Scholarship agent timed out after 300 seconds")
        return (
            "The search timed out before completion. "
            "Please try a narrower query (fewer universities or a more specific field)."
        )
    except RuntimeError as e:
        if "[LIMIT]" in str(e):
            logger.warning("ToolCallGuard fired: %s", e)
            return (
                "The agent reached its tool-call budget. "
                "Please retry — if this persists, try a narrower query."
            )
        logger.error("Scholarship agent runtime error: %s", e)
        return (
            "The search hit an internal processing error. "
            "Please retry, and if it persists, try a narrower query."
        )
    except Exception as e:
        logger.error("Scholarship agent failed: %s", e)
        return (
            "The search hit an internal processing error. "
            "Please retry, and if it persists, try a narrower query."
        )
