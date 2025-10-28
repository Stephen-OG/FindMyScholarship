from agents import Agent, AgentOutputSchema
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from utils.crawler import crawl_university_funding

# Crawler Agent
crawler_instructions = """You are a crawler agent that coordinates between different research tools.

DECISION PROCESS:
1. Use crawl_university_funding to search for funding opportunities on those domains after analysing the user needs
2. Return comprehensive results including both domains and funding info

The keyword analysis helps you focus on what matters most to the user."""

class FundingPage(BaseModel):
    url: str
    "Url of the funding page"
    title: str
    "Title of the funding page"
    preview: str
    "Summary of the page"

class UniversityResult(BaseModel):
    school: str
    "The name of the school"
    domain: str
    "The school's official domain"
    funding_pages: List[FundingPage]
    "The number of funding pages found"

class CrawlerResult(BaseModel):
    universities: List[UniversityResult]
    "Name of Universities found"
    search_strategy: Optional[str]
    "search strategy"
    total_funding_pages: Optional[int]
    "Total funding page found"
    keyword_analysis: Optional[Dict[str, Any]]
    "Keywords searched for"

crawler_agent = Agent(
    name="Crawler Agent",
    instructions=crawler_instructions,
    tools=[crawl_university_funding],
    model="gpt-4o-mini",
    output_type=AgentOutputSchema(CrawlerResult, strict_json_schema=False)
)