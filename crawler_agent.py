from agents import Agent
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from utils.crawler import crawl_university_funding

# Crawler Agent
crawler_instructions = """You are a crawler agent that coordinates between different research tools.
Use crawl_university_funding to search for funding opportunities on those domains

The keyword analysis helps you focus on what matters most to the user."""

class FundingPage(BaseModel):
    url: str
    title: str
    preview: str

class UniversityResult(BaseModel):
    school: str
    domain: str
    funding_pages: List[FundingPage]

class CrawlerResult(BaseModel):
    universities: List[UniversityResult]
    search_strategy: str
    total_funding_pages: int
    keyword_analysis: Optional[Dict[str, Any]]

crawler_agent = Agent(
    name="Crawler Agent",
    instructions=crawler_instructions,
    tools=crawl_university_funding,
    model="gpt-4o-mini",
    output_type=CrawlerResult
)