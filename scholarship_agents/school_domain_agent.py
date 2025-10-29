import os
from typing import List, Optional
from urllib.parse import urlparse

from agents import Agent, AgentOutputSchema, function_tool
from dotenv import load_dotenv
from pydantic import BaseModel
from serpapi.google_search import GoogleSearch

load_dotenv(override=True)

SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")


@function_tool
def find_university_domain(school: str, country: Optional[str] = None, num: int = 5) -> List[str]:
    """Find university domains using SerpAPI"""
    
    query_parts = [school, "official site", "scholarship", "funding"]
    if country:
        query_parts.append(country)
    query = " ".join(query_parts)

    search = GoogleSearch({"q": query, "api_key": SERPAPI_KEY, "num": num})
    results = search.get_dict()

    urls = []
    if "organic_results" in results:
        for r in results["organic_results"]:
            if "link" in r:
                urls.append(r["link"])

    # BETTER FILTERING - Check for school name keywords in domain
    cleaned = []
    school_keywords = school.lower().split()  # ["university", "of", "exeter"]
    
    for u in urls:
        netloc = urlparse(u).netloc.lower()
        
        # Check if meaningful keywords from school name appear in domain
        # Skip common words like "of", "the", "university"
        meaningful_keywords = [k for k in school_keywords if k not in ["of", "the", "university", "college"]]
        
        # Domain should contain at least one meaningful keyword OR be a .ac.uk domain
        if any(keyword in netloc for keyword in meaningful_keywords) or netloc.endswith(".ac.uk"):
            base = f"https://{netloc}"
            if base not in cleaned:
                cleaned.append(base)
    
    # If no results, fall back to more permissive check
    if not cleaned:
        for u in urls:
            netloc = urlparse(u).netloc.lower()
            if "univ" in netloc or ".edu" in netloc or ".ac." in netloc:
                base = f"https://{netloc}"
                if base not in cleaned:
                    cleaned.append(base)

    return cleaned[:num]
    
# def find_university_domain(school: str, country: Optional[str] = None, num: int = 5) -> List[str]:
#     """
#     Find likely university domains for any school in any country using SerpAPI.
#     - school: "University of Melbourne"
#     - country: "Australia" (optional)
#     Returns: list of domains (https://...)
#     """

#     query_parts = [school, "official site", "scholarship", "funding"]
#     if country:
#         query_parts.append(country)
#     query = " ".join(query_parts)

#     search = GoogleSearch({"q": query, "api_key": SERPAPI_KEY, "num": num})
#     results = search.get_dict()
#     # print(results)

#     urls = []
#     if "organic_results" in results:
#         for r in results["organic_results"]:
#             if "link" in r:
#                 urls.append(r["link"])

#     # Filter to probable university domains
#     cleaned = []
#     for u in urls:
#         netloc = urlparse(u).netloc.lower()
#         if any(x in netloc for x in [school.lower().replace(" ", ""), "univ", "edu", "ac."]):
#             base = f"https://{netloc}"
#             if base not in cleaned:
#                 cleaned.append(base)

#     return cleaned[:num]


class SchoolAndDomain(BaseModel):
    school: str
    "The name of the school"
    domain: str
    "The school's official domain"


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

class MultipleSchoolsAndDomains(BaseModel):
    schools: List[SchoolAndDomain]
    "List of schools and their domains"
    #search_type: str = "searched"
    search_type: str
    "Either 'explicit' (schools were explicitly mentioned) or 'searched' (schools were found via search)"


search_agent = Agent(
    name="Smart university domain finder",
    instructions=search_agent_instructions,
    tools=[find_university_domain],
    model="gpt-4o-mini",
    output_type=AgentOutputSchema(MultipleSchoolsAndDomains, strict_json_schema=False),
)
