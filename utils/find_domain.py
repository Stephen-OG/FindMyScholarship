import os
import re
from typing import List, Optional
from urllib.parse import urlparse

from agents import function_tool
from dotenv import load_dotenv
from serpapi.google_search import GoogleSearch

from utils.logger import logger

load_dotenv(override=True)

SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")
_domain_search_cache: dict[str, List[str]] = {}

_SCHOOL_STOPWORDS = {
    "of", "the", "and", "for", "at", "in", "on",
    "university", "college", "institute", "school",
}
_NON_UNIVERSITY_HINTS = {
    "research", "institute", "company", "corp", "inc", "foundation", "ngo",
}
_UNIVERSITY_HINTS = {
    "university", "univ", "college", "faculty", "campus", "edu", ".ac.",
}


def _normalize_netloc(url: str) -> str:
    netloc = urlparse(url).netloc.lower().strip()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def _school_tokens(school: str) -> List[str]:
    raw_tokens = re.findall(r"[a-z0-9]+", school.lower())
    return [t for t in raw_tokens if len(t) > 2 and t not in _SCHOOL_STOPWORDS]


def _is_probable_university_domain(netloc: str, school_tokens: List[str]) -> bool:
    domain_compact = netloc.replace("-", "").replace(".", "")
    token_match = any(token in domain_compact for token in school_tokens)
    has_uni_hint = any(hint in netloc for hint in _UNIVERSITY_HINTS)
    has_academic_tld = ".edu" in netloc or ".ac." in netloc or netloc.endswith(".ac.uk")
    has_non_uni_hint = any(hint in netloc for hint in _NON_UNIVERSITY_HINTS)

    # Allow known academic patterns or clear school-name match.
    if not (token_match or has_uni_hint or has_academic_tld):
        return False

    # Block clearly non-university org domains unless they also look academic.
    if has_non_uni_hint and not (has_uni_hint or has_academic_tld):
        return False

    return True


@function_tool
def find_university_domain(school: str, country: Optional[str] = None) -> List[str]:
    """Find university domains using SerpAPI"""
    num:int = 5
    school_clean = (school or "").strip()
    if len(school_clean) < 2:
        logger.info("Skipping domain lookup for empty/invalid school name")
        return []

    cache_key = f"{school_clean.lower()}|{(country or '').strip().lower()}"
    if cache_key in _domain_search_cache:
        cached = _domain_search_cache[cache_key]
        logger.info(f"Using cached domains for '{school_clean}': {cached}")
        return cached[:num]

    logger.info(f"Looking up domains for '{school_clean}'")

    query_parts = [school_clean, "official site", "scholarship", "funding"]

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

    cleaned: List[str] = []
    seen: set[str] = set()
    school_tokens = _school_tokens(school_clean)

    for u in urls:
        netloc = _normalize_netloc(u)
        if not netloc:
            continue
        if _is_probable_university_domain(netloc, school_tokens):
            base = f"https://{netloc}"
            if base not in seen:
                cleaned.append(base)
                seen.add(base)
    
    # If no results, fall back to more permissive check
    if not cleaned:
        for u in urls:
            netloc = _normalize_netloc(u)
            if not netloc:
                continue
            if "univ" in netloc or ".edu" in netloc or ".ac." in netloc or any(token in netloc for token in school_tokens):
                base = f"https://{netloc}"
                if base not in seen:
                    cleaned.append(base)
                    seen.add(base)
                    
    logger.info(f"Cleaned domains: {cleaned}")
    _domain_search_cache[cache_key] = cleaned[:num]
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
