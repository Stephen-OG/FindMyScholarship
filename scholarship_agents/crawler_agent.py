
from agents import Agent, AgentOutputSchema
from dotenv import load_dotenv

from models.crawler_model import CrawlerResult
from utils.constants import CRAWLER_INSTRUCTIONS
from utils.crawler import crawl_university_funding
from utils.logger import logger

load_dotenv()

logger.info("Starting crawler agent")

crawler_instructions = CRAWLER_INSTRUCTIONS

# Create the crawler agent
crawler_agent = Agent(
    name="Crawler Agent",
    instructions=crawler_instructions,
    tools=[crawl_university_funding],
    model="gpt-4o-mini",
    output_type=AgentOutputSchema(CrawlerResult, strict_json_schema=False),
)