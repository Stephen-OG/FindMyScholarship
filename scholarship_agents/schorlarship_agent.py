# # scholarship_agents/schorlarship_agent.py
# """
# Main orchestrator agent for FindMyScholarship
# Updated to pass user query to crawler for keyword extraction
# """

# from agents import Agent, Runner

# from scholarship_agents.analyzer_agent import analyzer_agent
# from scholarship_agents.crawler_agent import crawler_agent
# from scholarship_agents.school_domain_agent import search_agent

# #Convert sub-agents to tools
# search_agent_tool = search_agent.as_tool(
#     tool_name="university_domain_search",
#     tool_description="Find university domains for given schools or research topics. Returns school names, user's query and their official domains.",
# )


# crawler_agent_tool = crawler_agent.as_tool(
#     tool_name="crawl_universities",
#     tool_description="""Crawl a single university website to discover funding opportunities with intelligent keyword extraction.
    
#     CRITICAL: Always provide BOTH parameters:
#     1. university_domain: The domain to crawl (e.g., "https://mit.edu")
#     2. user_query: The user's original search query for keyword extraction
    
#     The crawler will:
#     - Extract relevant keywords from the query (degree level, field of study, location, etc.)
#     - Prioritize pages containing those keywords
#     - Score results by relevance to the query
#     - Return structured funding opportunities with URLs, titles, and previews
    
#     Example usage:
#     crawl_universities(
#         university_domain="https://mit.edu",
#         user_query="PhD funding in machine learning for international students"
#     )
    
#     Call this tool separately for each university you want to search.
    
#     Returns: Funding pages found at that specific university, sorted by relevance score.
#     """,
# )

# analyzer_agent_tool = analyzer_agent.as_tool(
#     tool_name="analyze_funding_pages",
#     tool_description="""Analyze crawled funding pages to extract structured information.
    
#     Takes raw page data from crawler and extracts:
#     - Specific scholarship/funding names
#     - Degree levels, fields, eligibility
#     - Funding amounts and deadlines
#     - Application process
#     - Relevance to user's query
    
#     Call this AFTER crawling to get detailed, structured funding information.
    
#     Example: analyze_funding_pages(crawler_results=..., user_query="PhD in biology")
#     """,
# )

# tools = [search_agent_tool, crawler_agent_tool, analyzer_agent_tool]

# system_prompt = """
# You are FindMyScholarship AI - an intelligent assistant that helps students discover funding opportunities.

# APP WORKFLOW (3-STAGE PIPELINE):
# 1. FIND DOMAINS: Use university_domain_search to get university websites
#    - If user mentions specific universities, find only those
#    - If user describes a topic, search for relevant universities

# 2. CRAWL PAGES: Use crawl_universities to find funding pages
#    - Always pass the user's original query
#    - Crawl MAX 3-4 universities per call
#    - This returns RAW page data (URLs, titles, text snippets)

# 3. ANALYZE CONTENT: Use analyze_funding_pages to extract structured details
#    - Pass the crawler results AND user query
#    - This extracts specific scholarship names, amounts, deadlines, eligibility
#    - Returns organized, detailed funding information

# 4. PRESENT RESULTS: Show findings in a clear, helpful format

# CONTEXT MANAGEMENT:
# - Break large requests into batches (max 3-4 universities per crawl call)
# - Always analyze the crawled results to get structured details
# - The analyzer extracts specific information you can present clearly

# RESPONSE FORMAT:
# Present results by university with:
# - University name and relevant funding pages
# - Specific scholarship/funding names with details:
#   * Degree level (PhD, Masters, etc.)
#   * Funding amount (be specific: "£18,000/year" not just "funding")
#   * Eligibility requirements
#   * Deadlines (if available)
#   * Link to apply
# - Highlight the most relevant opportunities first
# - Be encouraging and specific

# EXAMPLE FLOW:
# User: "PhD funding in computer science at MIT and Stanford"

# 1. Search: university_domain_search("MIT", "Stanford")
#    → Returns: ["https://mit.edu", "https://stanford.edu"]

# 2. Crawl: crawl_universities(domains=[...], user_query="PhD funding in computer science at MIT and Stanford")
#    → Returns: List of funding pages with URLs and text

# 3. Analyze: analyze_funding_pages(crawler_results=..., user_query="PhD funding in computer science")
#    → Returns: Structured details (names, amounts, deadlines, etc.)

# 4. Present: Show specific opportunities with all relevant details

# ALWAYS USE ALL THREE STAGES for complete results!
# """


# # Create main orchestrator agent
# schorlaship_agent = Agent(
#     name="Scholarship Researcher",
#     instructions=system_prompt,
#     tools=tools,
#     model="gpt-4o-mini",
# )


# async def chat(message, history):
#     """
#     Handles user input and previous chat history for FindMyScholarship AI.
#     Compatible with Gradio list or dict chat history formats.
#     """
#     messages = [{"role": "system", "content": system_prompt}]

#     # Process history
#     for turn in history:
#         # If turn is a list/tuple (older Gradio format)
#         if isinstance(turn, (list, tuple)) and len(turn) >= 2:
#             user_msg = turn[0]
#             ai_msg = turn[1]

#         # If turn is a dict (newer Gradio format)
#         elif isinstance(turn, dict):
#             if turn.get("role") == "user":
#                 user_msg = turn.get("content") or turn.get("message")
#                 ai_msg = None
#             elif turn.get("role") == "assistant":
#                 user_msg = None
#                 ai_msg = turn.get("content") or turn.get("message")
#             else:
#                 continue
#         else:
#             continue

#         if user_msg:
#             messages.append({"role": "user", "content": user_msg})
#         if ai_msg:
#             messages.append({"role": "assistant", "content": ai_msg})

#     # Append latest user message
#     messages.append({"role": "user", "content": message})

#     # Run the agent
#     response = await Runner.run(schorlaship_agent, messages)
#     return response.final_output









from agents import Agent, Runner

from scholarship_agents.crawler_agent import crawler_agent
from scholarship_agents.school_domain_agent import search_agent

search_agent_tool = search_agent.as_tool(
    tool_name="university_domain_search",
    tool_description="Find university domains for given schools or research topics",
)

crawler_agent_tool = crawler_agent.as_tool(
    tool_name="Crawler",
    tool_description="Crawl university domains for given relevant keywords or research topics",
)

tools = [search_agent_tool, crawler_agent_tool]

system_prompt = """
You are FindMyScholarship AI - an intelligent assistant that helps students discover funding opportunities.

APP WORKFLOW:
1. USER INPUT: Student describes what they're looking for (field of study, degree level, preferred universities, etc.)
2. UNIVERSITY IDENTIFICATION: Extract and identify relevant universities from the query
3. DOMAIN DISCOVERY: Use the university_domain_search tool to find official university websites
4. SMART CRAWLING: Use the crawl_universities tool to search university websites
   - CRITICAL: Always pass the user's original query to crawl_universities for keyword extraction
   - CRITICAL: Crawl MAX 3-4 universities per call to avoid exceeding context limits
   - If user asks for many universities, make MULTIPLE separate crawl calls
   - Each university returns up to 40 pages ranked by relevance (scores 5-100+)
   - Example: For 6 universities, make 2 calls with 3 domains each
5. RESULTS COMPILATION: Present structured funding opportunities with URLs, titles, and relevance

CONTEXT MANAGEMENT:
- Each university returns TOP 10 most relevant pages (ranked automatically)
- DO NOT crawl more than 3-4 universities in a single tool call
- For many universities, use multiple sequential calls:
  * Call 1: First 3 universities
  * Call 2: Next 3 universities
  * etc.

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

EXAMPLE FLOW:
User: "PhD funding in machine learning at MIT, Stanford, Berkeley, CMU, and Harvard"
1. Use university_domain_search to get all 5 domains
2. Call crawl_universities(domains=[MIT, Stanford, Berkeley], user_query=...)
3. Call crawl_universities(domains=[CMU, Harvard], user_query=...)
4. Present combined results grouped by university

REMEMBER: Break large requests into smaller batches to avoid context limits!
"""

schorlaship_agent = Agent(
    name="Schorlaship Researcher", instructions=system_prompt, tools=tools, model="gpt-4o-mini"
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
            user_msg = turn.get("user") or turn.get("message") if turn.get("role") == "user" else None
            ai_msg = turn.get("assistant") or turn.get("message") if turn.get("role") == "assistant" else None

        else:
            continue  # skip malformed turns

        if user_msg:
            messages.append({"role": "user", "content": user_msg})
        if ai_msg:
            messages.append({"role": "assistant", "content": ai_msg})

    # Append latest user message
    messages.append({"role": "user", "content": message})

    # Run the agent
    response = await Runner.run(schorlaship_agent, messages)
    return response.final_output
