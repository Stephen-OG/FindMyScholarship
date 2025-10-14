from agents import Agent, function_tool
from pydantic import BaseModel
from serpapi.google_search import GoogleSearch

from urllib.parse import urlparse
from dateutil import parser as dateparser
import os
from typing import Optional, List
from dotenv import load_dotenv
load_dotenv(override=True)

SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")

@function_tool
def find_university_domain(school: str, country: Optional[str]=None, num: int=5) -> List[str]:
    """
    Find likely university domains for any school in any country using SerpAPI.
    - school: "University of Melbourne"
    - country: "Australia" (optional)
    Returns: list of domains (https://...)
    """

    query_parts = [school, "official site", "scholarship", "funding"]
    if country:
        query_parts.append(country)
    query = " ".join(query_parts)

    search = GoogleSearch({
        "q": query,
        "api_key": SERPAPI_KEY,
        "num": num
    })
    results = search.get_dict()
    print(results)

    urls = []
    if "organic_results" in results:
        for r in results["organic_results"]:
            if "link" in r:
                urls.append(r["link"])

    # Filter to probable university domains
    cleaned = []
    for u in urls:
        netloc = urlparse(u).netloc.lower()
        if any(x in netloc for x in [school.lower().replace(" ", ""), "univ", "edu", "ac."]):
            base = f"https://{netloc}"
            if base not in cleaned:
                cleaned.append(base)

    return cleaned[:num]


class SchoolAndDomain(BaseModel):
    school: str
    "The name of the school"
    domain: str
    "The school's official domain"

search_agent_instructions = """You are a university domain research assistant. 

FOLLOW THESE RULES:
1. FIRST, check if specific school names are EXPLICITLY mentioned in the query
2. IF explicit schools are mentioned:
   - Return ONLY those explicitly mentioned schools and their domains
   - Do NOT add any other schools
3. IF NO explicit schools are mentioned:
   - Search for relevant schools based on the query context
   - Return the most relevant schools and their domains

Examples:
- "Find MIT and Stanford domains" → Return: MIT, Stanford (only explicit)
- "University of Toronto website" → Return: University of Toronto (only explicit)
- "Top AI PhD programs" → Return: List of relevant schools (no explicit ones)
- "Machine learning scholarships in UK" → Return: List of relevant UK schools"""

class MultipleSchoolsAndDomains(BaseModel):
    schools: List[SchoolAndDomain]
    "List of schools and their domains"
    search_type: str
    "Either 'explicit' (schools were explicitly mentioned) or 'searched' (schools were found via search)"

search_agent = Agent(
    name="Smart university domain finder",
    instructions=search_agent_instructions,
    tools=[find_university_domain],
    model="gpt-4o-mini",
    output_type=MultipleSchoolsAndDomains
)