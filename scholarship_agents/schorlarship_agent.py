import asyncio

from agents import Agent, Runner

from scholarship_agents.school_domain_agent import search_agent
from utils.analyzer import analyze_crawler_results
from utils.crawler import crawl_universities_formatted
from utils.logger import logger

logger.info("Starting scholarship agent")

search_agent_tool = search_agent.as_tool(
    tool_name="university_domain_search",
    tool_description="Find university domains for given schools or research topics. Call ONCE per query to get all relevant universities. Returns list of universities with their official domains.",
    max_turns=2,
)

tools = [search_agent_tool, crawl_universities_formatted, analyze_crawler_results]

system_prompt = """
You are FindMyScholarship AI - an intelligent assistant that helps students discover funding opportunities.

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
   - If you have many universities, make MULTIPLE separate crawl_universities_formatted calls (one per batch)
   - Each university can return up to 40 crawled pages from a crawl budget of up to 40 visited pages
   - Example: For 6 universities, make 2 Crawler calls: First 3, then next 3
   - STOP CRAWLING once all universities have been crawled
4. ANALYZE CONTENT: Use analyze_crawler_results ONCE with all crawled results
   - Pass the `universities` list from the crawler output in step 3 AND the user query
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
- Highlight the most relevant opportunities first (based on relevance scores)
- Include direct links to all funding pages
- Provide context from page previews
- Be encouraging and helpful in tone
- If few results found, suggest alternative searches
- If the analyzer reports zero opportunities, clearly say no relevant funding opportunities were found
- When zero opportunities are found, DO NOT present generic research/study/program pages as scholarship findings
- When zero opportunities are found, suggestions must be framed as next steps, not as discovered results

EXAMPLE FLOW (EXECUTE ONCE, THEN STOP):
User: "PhD funding in machine learning at MIT, Stanford, Berkeley, CMU, and Harvard"

Step 1: Call university_domain_search ONCE → Returns 5 universities
Step 2: Call crawl_universities_formatted with first 3 universities → Returns pages
Step 3: Call crawl_universities_formatted with remaining 2 universities → Returns pages
Step 4: Call analyze_crawler_results ONCE with ALL results from steps 2-3 → Returns analyzed data
Step 5: Present results to user → STOP (workflow complete)

DO NOT:
- Call university_domain_search again after step 1
- Call crawl_universities_formatted again after step 3 (you already have all pages)
- Call analyze_crawler_results again after step 4 (analysis is done)
- Loop back to any previous step

REMEMBER: Execute each step ONCE, then move to the next. After presenting results, STOP.
"""

scholarship_agent = Agent(
    name="Scholarship Researcher", instructions=system_prompt, tools=tools, model="gpt-4o-mini"
)


async def chat(message, history):
    """
    Handles user input and previous chat history for FindMyScholarship AI.
    Compatible with Gradio list or dict chat history formats.
    """
    messages = [{"role": "system", "content": system_prompt}]

    for turn in history:
        # If turn is a list/tuple
        if isinstance(turn, (list, tuple)) and len(turn) >= 2:
            user_msg = turn[0]
            ai_msg = turn[1]

        # If turn is a dict (newer Gradio format)
        elif isinstance(turn, dict):
            if turn.get("role") == "user":
                user_msg = turn.get("user") or turn.get("content") or turn.get("message")
                ai_msg = None
            elif turn.get("role") == "assistant":
                user_msg = None
                ai_msg = turn.get("assistant") or turn.get("content") or turn.get("message")
            else:
                user_msg = None
                ai_msg = None

        else:
            continue  # skip malformed turns

        if user_msg:
            messages.append({"role": "user", "content": user_msg})
        if ai_msg:
            messages.append({"role": "assistant", "content": ai_msg})

    # Append latest user message
    messages.append({"role": "user", "content": message})

    # Run the agent with hard limits so UI does not appear stuck on tool loops.
    try:
        response = await asyncio.wait_for(
            Runner.run(scholarship_agent, messages, max_turns=8),
            timeout=300,
        )
        return response.final_output
    except asyncio.TimeoutError:
        logger.error("Scholarship agent timed out after 300 seconds")
        return (
            "The search timed out before completion. "
            "Please try a narrower query (fewer universities or a more specific field)."
        )
    except Exception as e:
        logger.error(f"Scholarship agent failed: {e}")
        return (
            "The search hit an internal processing error. "
            "Please retry, and if it persists, try a narrower query."
        )
