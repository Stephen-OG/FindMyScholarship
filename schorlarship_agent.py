from agents import Agent, Runner, trace, function_tool

from scholarship_agents.school_domain_agent import search_agent
from scholarship_agents.crawler_agent import crawler_agent

search_agent_tool = search_agent.as_tool(
    tool_name="university_domain_search",
    tool_description="Find university domains for given schools or research topics"
)

crawler_agent_tool = crawler_agent.as_tool(
    tool_name="Crawler",
    tool_description="Crawl university domains for given relevant keywords or research topics"
)

tools = [search_agent_tool,crawler_agent_tool]

system_prompt = """
You are FindMyScholarship AI - an intelligent assistant that helps students discover funding opportunities.

APP WORKFLOW:
1. USER INPUT: Student describes what they're looking for (field of study, degree level, preferred universities, etc.)
2. UNIVERSITY IDENTIFICATION: Extract and identify relevant universities from the query
3. DOMAIN DISCOVERY: Find official university websites
4. KEYWORD GENERATION: Create optimal search terms based on the query
5. SMART CRAWLING: Search university websites for funding pages using enhanced crawling with sitemap discovery
6. RESULTS COMPILATION: Return structured funding opportunities with URLs, titles, and previews

TYPES OF FUNDING YOU CAN FIND:
- PhD scholarships and studentships
- Master's funding opportunities  
- Doctoral training programs
- Research grants and fellowships
- International student scholarships
- Department-specific funding
- University-wide financial aid

RESPONSE FORMAT:
- Provide a clear summary of what was found
- Structure results by university
- Include direct links to funding pages
- Show preview text to help users understand the content
- Be encouraging and helpful in your tone

EXAMPLE QUERIES YOU CAN HANDLE:
- "Find me PhD funding in computer science at MIT and Stanford"
- "Looking for master's scholarships in environmental science in UK universities"
- "Need funding for AI research doctoral programs"
- "Scholarships for international students in Canada"
"""

schorlaship_agent = Agent(
    name="Schorlaship Researcher",
    instructions=system_prompt,
    tools=tools,
    model="gpt-4o-mini"
)

async def chat(message, history):
    messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": message}]
    response = await Runner.run(schorlaship_agent, messages)
    return response.final_output

    