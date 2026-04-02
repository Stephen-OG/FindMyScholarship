import asyncio
from typing import Any, AsyncIterator, Optional

from agents import Agent, RunHooks, Runner, handoff

from scholarship_agents.explorer_agent import explorer_agent
from scholarship_agents.school_domain_agent import search_agent
from utils.analyzer import analyze_crawler_results
from utils.crawl import crawl_universities_formatted
from utils.logger import logger

logger.info("Starting scholarship agent")

search_agent_tool = search_agent.as_tool(
    tool_name="university_domain_search",
    tool_description="Find university domains for given schools or research topics. Call ONCE per query to get all relevant universities. Returns list of universities with their official domains.",
    max_turns=5,
)

tools = [search_agent_tool, crawl_universities_formatted, analyze_crawler_results]

system_prompt = """
You are FindMyScholarship AI - an intelligent assistant that helps students discover funding opportunities.

🔑 KEYWORD EXTRACTION OPTIMIZATION:
- Keywords for this query have been pre-extracted by the system
- When you call crawl_universities_formatted: PASS the extracted_keywords from the context message
- When you call analyze_crawler_results: PASS the extracted_keywords from the context message
- This optimization reduces redundant LLM calls and improves efficiency

APP WORKFLOW (EXECUTE ONCE, THEN STOP):
1. USER INPUT: Student describes what they're looking for (field of study, degree level, preferred universities, etc.)
2. DOMAIN DISCOVERY: Use the university_domain_search tool ONCE to find all relevant university websites
   - This returns a list of universities and their domains
   - DO NOT call this tool multiple times for the same query
   - For broad topic queries (no explicit university names), limit to at most 5 universities
   - If the query is too broad/ambiguous, ask the user to narrow it before deep crawling
3. SMART CRAWLING: Use crawl_universities_formatted to search university websites
   - CRITICAL: Call crawl_universities_formatted ONCE per batch of universities (max 3-4 per call)
   - CRITICAL: Always pass the user's original query to the tool for keyword extraction
   - IMPORTANT: Pass extracted_keywords parameter (from context) to avoid re-extraction
   - If you have many universities, make MULTIPLE separate crawl_universities_formatted calls (one per batch)
   - Each university can return up to 40 crawled pages from a crawl budget of up to 40 visited pages
   - Example: For 6 universities, make 2 Crawler calls: First 3, then next 3
   - STOP CRAWLING once all universities have been crawled
4. ANALYZE CONTENT: Use analyze_crawler_results ONCE with all crawled results
   - Pass the `universities` list from the crawler output in step 3 AND the user query
   - IMPORTANT: Pass extracted_keywords parameter (from context) to avoid re-extraction
   - The tool will internally analyze the returned crawler pages and return a valid AnalyzerResult object
   - This extracts specific scholarship names, amounts, deadlines, eligibility
   - Returns organized, detailed funding information
5. PRESENT RESULTS: Format and present the analyzed results to the user
   - Group by university
   - Highlight most relevant opportunities
   - Include direct links
   - THEN STOP - do not call any more tools

CRITICAL STOPPING RULES:
- After step 2: DO NOT call university_domain_search again
- After step 3: DO NOT call crawl_universities_formatted again - you already have all results
- After step 4: DO NOT call analyze_crawler_results again - analysis is complete
- After step 5: STOP and present results - workflow is complete
- If runtime is getting long, return partial findings from completed universities instead of starting new crawling/analysis cycles

CONTEXT MANAGEMENT:
- Each university returns TOP pages ranked by relevance (automatically sorted)
- DO NOT crawl more than 3-4 universities in a single crawl_universities_formatted call
- For broad queries without explicit university names, do not exceed 5 universities total
- For many universities, use multiple sequential Crawler calls, then STOP
- The analyzer tool decides how to batch and filter page analysis internally

TYPES OF FUNDING YOU CAN FIND:
- PhD scholarships and studentships
- Master's funding opportunities
- Doctoral training programs
- Research grants and fellowships
- International student scholarships
- Department-specific funding
- University-wide financial aid

RESPONSE GUIDELINES:
- Start with a brief summary of what you found
- Group results by university
- Highlight the most relevant opportunities first
- Include direct links to all funding pages

FORMATTING RULES — CRITICAL:
- NEVER write "Not specified", "N/A", or "Unknown" for any field
- If a field (deadline, amount, eligibility) was not found on the page, OMIT it entirely — do not show the label at all
- For deadline: if not extracted, do NOT show a Deadline line — instead add one line: "→ Check the funding page for current deadlines"
- For amount: if not extracted, do NOT show an Amount line — instead add: "→ Contact the department for funding details"
- For eligibility: if not extracted, omit the line entirely
- For application process: ALWAYS show a direct link or clear next step — never leave this blank
- Each opportunity must end with a clear call to action: either a direct apply link or the exact page to visit

QUALITY RULES:
- If few results found, suggest specific alternative searches (different keywords, related departments, etc.)
- If the analyzer reports zero opportunities, clearly say no funding was found and give 2-3 concrete next steps the user can take
- DO NOT present generic program pages as scholarship findings
- Every result must be actionable — the user should know exactly what to do next

EXAMPLE FLOW (EXECUTE ONCE, THEN STOP):
User: "PhD funding in machine learning at MIT, Stanford, Berkeley, CMU, and Harvard"

Step 1: Call university_domain_search ONCE → Returns 5 universities
Step 2: Call crawl_universities_formatted with first 3 universities (pass extracted_keywords) → Returns pages
Step 3: Call crawl_universities_formatted with remaining 2 universities (pass extracted_keywords) → Returns pages
Step 4: Call analyze_crawler_results ONCE with ALL results from steps 2-3 (pass extracted_keywords) → Returns analyzed data
Step 5: Present results to user → STOP (workflow complete)

DO NOT:
- Call university_domain_search again after step 1
- Call crawl_universities_formatted again after step 3 (you already have all pages)
- Call analyze_crawler_results again after step 4 (analysis is done)
- Loop back to any previous step

REMEMBER: Execute each step ONCE, then move to the next. After presenting results, hand off to the Results Explorer.

HANDOFF RULES:
- After presenting the full results in Step 5, ALWAYS hand off to results_explorer
- The results_explorer will handle all follow-up questions: filtering, comparing, explaining, next-step advice
- Do NOT hand off before results are ready — complete the full search first
- If the user asks a follow-up question AND results are already in the conversation, hand off immediately without re-crawling
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


def _build_messages(message: str, history, *, use_explorer: bool = False) -> list:
    """Convert Gradio history + current message into OpenAI message list."""
    from scholarship_agents.explorer_agent import explorer_instructions

    prompt = explorer_instructions if use_explorer else system_prompt
    messages = [{"role": "system", "content": prompt}]
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
            messages.append({"role": "user", "content": user_msg})
        if ai_msg:
            messages.append({"role": "assistant", "content": ai_msg})
    messages.append({"role": "user", "content": message})
    return messages


def _is_followup(history) -> bool:
    """
    Returns True if the conversation already contains a completed search result,
    meaning the user is asking a follow-up question rather than starting a new search.

    Heuristic: the assistant has already replied at least once with a substantive
    message (>200 chars), indicating the search pipeline has run.
    """
    for turn in history:
        ai_msg = None
        if isinstance(turn, (list, tuple)) and len(turn) >= 2:
            ai_msg = turn[1]
        elif isinstance(turn, dict) and turn.get("role") == "assistant":
            ai_msg = turn.get("content", "")
        if ai_msg and len(str(ai_msg)) > 200:
            return True
    return False


async def chat_stream(message: str, history) -> AsyncIterator[str]:
    """
    Streaming version of chat().

    Yields incremental status strings while the agent runs tools, then
    yields the final answer once the agent finishes.  Each yielded value
    is the *full current* assistant bubble text (Gradio streaming convention).

    Routes follow-up questions directly to explorer_agent to avoid re-crawling.
    """
    is_followup = _is_followup(history)
    active_agent = explorer_agent if is_followup else scholarship_agent
    messages = _build_messages(message, history, use_explorer=is_followup)
    progress_queue: asyncio.Queue[Optional[str]] = asyncio.Queue()
    # Explorer has no tools so the guard is only needed for the search agent
    guard = ToolCallGuard(progress_queue=progress_queue) if not is_followup else None

    _SENTINEL = object()
    accumulated_status: list[str] = []

    if is_followup:
        logger.info("Follow-up detected — routing to Results Explorer (no crawl)")

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
