from typing import Any, Dict, List, Optional

from agents import Agent, AgentOutputSchema
from dotenv import load_dotenv
from pydantic import BaseModel

from utils.crawler import crawl_university_funding

load_dotenv()

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


class FundingPage(BaseModel):
    url: str
    "URL of the funding page"
    title: str
    "Title of the funding page"
    preview: str
    "Summary/preview of the page content"
    relevance_score: Optional[int] = None
    "Relevance score (higher = more relevant to query)"


class UniversityResult(BaseModel):
    school: str
    "The name of the school"
    domain: str
    "The school's official domain"
    funding_pages: List[FundingPage]
    "List of funding pages found"
    summary: Optional[str] = None
    "Brief summary of funding opportunities at this university"


class CrawlerResult(BaseModel):
    universities: List[UniversityResult]
    "Universities crawled with their funding pages"
    search_strategy: Optional[str] = None
    "Description of the search strategy used"
    total_funding_pages: int = None
    "Total number of funding pages found across all universities"
    keyword_analysis: Optional[Dict[str, Any]] = None
    "Keywords extracted and used for targeted crawling"
    relevance_tiers: Optional[Dict[str, int]] = None
    "Count of pages in each relevance tier: exceptional (100+), high (50-99), moderate (5-49)"

# Create the crawler agent
crawler_agent = Agent(
    name="Crawler Agent",
    instructions=crawler_instructions,
    tools=[crawl_university_funding],
    model="gpt-4o-mini",
    output_type=AgentOutputSchema(CrawlerResult, strict_json_schema=False),
)