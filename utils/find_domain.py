import os
from typing import List, Optional
from urllib.parse import urlparse

from agents import function_tool
from dotenv import load_dotenv
from serpapi.google_search import GoogleSearch

from utils.logger import logger

load_dotenv(override=True)

SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")


@function_tool
def find_university_domain(school: str, country: Optional[str] = None) -> List[str]:
    """Find university domains using SerpAPI"""
    num:int = 5
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
                    
    logger.info(f"Cleaned domains: {cleaned}")
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