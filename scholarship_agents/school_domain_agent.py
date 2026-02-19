from agents import Agent, AgentOutputSchema
from dotenv import load_dotenv

from models.domain_finder_model import MultipleSchoolsAndDomains
from utils.constants import SEARCH_AGENT_INSTRUCTIONS
from utils.find_domain import find_university_domain
from utils.logger import logger

load_dotenv(override=True)

logger.info("Starting school domain agent")

search_agent_instructions = SEARCH_AGENT_INSTRUCTIONS

search_agent = Agent(
    name="Smart university domain finder",
    instructions=search_agent_instructions,
    tools=[find_university_domain],
    model="gpt-4o-mini",
    output_type=AgentOutputSchema(MultipleSchoolsAndDomains, strict_json_schema=False),
)
