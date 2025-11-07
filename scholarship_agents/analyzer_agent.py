
from typing import List, Optional

from agents import Agent, AgentOutputSchema
from pydantic import BaseModel

from utils.analyzer import analyze_funding_page


# Pydantic models for structured output
class FundingOpportunity(BaseModel):
    name: str
    "Name of the scholarship or funding program"
    degree_level: str
    "Degree level (PhD, Masters, etc.)"
    field: Optional[str] = None
    "Academic field or discipline"
    eligibility: str
    "Eligibility requirements"
    amount: str
    "Funding amount or type"
    deadline: Optional[str] = None
    "Application deadline"
    for_international: Optional[bool] = None
    "Whether available to international students"
    application_process: str
    "How to apply"

class AnalyzedFundingPage(BaseModel):
    url: str
    "Page URL"
    title: str
    "Page title"
    opportunities: List[FundingOpportunity]
    "List of funding opportunities found on this page"
    page_summary: str
    "Brief summary of the page"
    relevance_to_query: str
    "Relevance to user's query (High/Medium/Low)"

class UniversityFundingAnalysis(BaseModel):
    university: str
    "University name"
    domain: str
    "University domain"
    analyzed_pages: List[AnalyzedFundingPage]
    "Detailed analysis of each funding page"
    total_opportunities: int
    "Total number of distinct funding opportunities found"
    summary: str
    "Overall summary of funding available at this university"
    best_matches: List[str]
    "Names of the top 3 most relevant opportunities for the user"

class AnalyzerResult(BaseModel):
    universities: List[UniversityFundingAnalysis]
    "Analyzed funding information for each university"
    overall_summary: str
    "Summary across all universities"
    total_opportunities_found: int
    "Total opportunities across all universities"

# Agent instructions
analyzer_instructions = """You are a funding analysis expert that extracts structured information from scholarship pages.

YOUR TASK:
1. Receive funding pages (URLs, titles, and content) from the crawler
2. Use analyze_funding_page to extract structured details from each page
3. Organize the information by university
4. Identify the most relevant opportunities based on the user's query
5. Provide a comprehensive summary

WHAT TO EXTRACT:
- Specific scholarship/funding names
- Degree levels (PhD, Masters, etc.)
- Academic fields/disciplines
- Eligibility criteria
- Funding amounts (be specific: "£18,000/year" not just "stipend")
- Application deadlines
- International student eligibility
- Application process

ANALYSIS GUIDELINES:
- Be thorough - extract ALL opportunities mentioned on each page
- Rate relevance to user's query (High/Medium/Low)
- Identify the top 3 best matches per university
- If information is missing, say "Not specified" rather than guessing
- Group opportunities by university for easy comparison

OUTPUT FORMAT:
- Detailed breakdown for each university
- Each funding opportunity fully described
- Clear indication of which opportunities best match the user's needs
- Overall summary highlighting key findings"""


# Create analyzer agent
analyzer_agent = Agent(
    name="Funding Analyzer",
    instructions=analyzer_instructions,
    tools=[analyze_funding_page],
    model="gpt-4o-mini",
    output_type=AgentOutputSchema(AnalyzerResult, strict_json_schema=False),
)