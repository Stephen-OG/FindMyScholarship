
from agents import Agent, AgentOutputSchema

from models.analyzer_model import AnalyzerResult
from utils.analyzer import analyze_funding_page, analyze_funding_pages_batch
from utils.constants import ANALYZER_INSTRUCTIONS
from utils.logger import logger

logger.info("Starting analyzer agent")

# Agent instructions
analyzer_instructions = ANALYZER_INSTRUCTIONS

# Create analyzer agent
analyzer_agent = Agent(
    name="Funding Analyzer",
    instructions=analyzer_instructions,
    tools=[analyze_funding_pages_batch, analyze_funding_page],  # Batch function first, single page as fallback
    model="gpt-4o-mini",
    output_type=AgentOutputSchema(AnalyzerResult, strict_json_schema=False),
)