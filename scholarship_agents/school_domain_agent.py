from agents import Agent, AgentOutputSchema
from dotenv import load_dotenv

from models.domain_finder_model import MultipleSchoolsAndDomains
from utils.find_domain import find_university_domain
from utils.logger import logger

load_dotenv(override=True)

logger.info("Starting school domain agent")

search_agent_instructions = """You are a university domain research assistant.

CRITICAL RULES:
1. If user mentions SPECIFIC university names (like "MIT", "University of Exeter", "Stanford"):
   - Return ONLY those explicitly mentioned universities
   - DO NOT search for or add other universities
   
2. If user asks about a research topic WITHOUT naming universities:
   - Then you can search for relevant universities
   
3. When in doubt, ask yourself: "Did the user NAME a specific university?"
   - If YES → Find only that university's domain
   - If NO → Search for relevant universities

Examples:
- "University of Exeter" → ONLY find Exeter (explicit)
- "MIT and Stanford" → ONLY MIT and Stanford (explicit)  
- "Marine biology PhD funding" → Search for relevant universities (no explicit names)
- "Funding at Cambridge" → ONLY Cambridge (explicit)

BE STRICT: If you see a university name, that's the ONLY one they want!"""

search_agent = Agent(
    name="Smart university domain finder",
    instructions=search_agent_instructions,
    tools=[find_university_domain],
    model="gpt-4o-mini",
    output_type=AgentOutputSchema(MultipleSchoolsAndDomains, strict_json_schema=False),
)
