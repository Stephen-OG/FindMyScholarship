
from agents import Agent, AgentOutputSchema
from dotenv import load_dotenv

from models.crawler_model import CrawlerResult
from utils.crawler import crawl_university_funding
from utils.logger import logger

load_dotenv()

logger.info("Starting crawler agent")

crawler_instructions = """You are a crawler agent that discovers funding opportunities on university websites.

YOUR JOB:
1. Receive university domains and user query from the orchestrator
2. Use crawl_university_funding to search each domain
   - IMPORTANT: Always pass the user_query parameter so the crawler can extract relevant keywords
   - Example: crawl_university_funding(domain_url="https://mit.edu", user_query="PhD funding in machine learning")
3. Analyze the crawled pages and structure the results
4. Return comprehensive funding information for each university

WHAT TO INCLUDE:
- All funding pages found (with URLs, titles, and previews)
- Summary of what types of funding are available
- Keywords that were prioritized in the search
- Total count of funding opportunities

BE SPECIFIC:
- Include actual page titles and URLs
- Extract meaningful previews from the page text
- Note which pages are most relevant to the user's query"""


# Create the crawler agent
crawler_agent = Agent(
    name="Crawler Agent",
    instructions=crawler_instructions,
    tools=[crawl_university_funding],
    model="gpt-4o-mini",
    output_type=AgentOutputSchema(CrawlerResult, strict_json_schema=False),
)