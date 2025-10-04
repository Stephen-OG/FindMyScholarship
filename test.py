# from agents import Agent, WebSearchTool, trace, Runner, gen_trace_id, function_tool, OpenAIChatCompletionsModel
# from agents.model_settings import ModelSettings
# from pydantic import BaseModel
# from dotenv import load_dotenv
# from openai import AsyncOpenAI
# from serpapi.google_search import GoogleSearch
# import re
# import time
# import requests
# import asyncio
# from urllib.parse import urljoin, urlparse
# from bs4 import BeautifulSoup
# from dateutil import parser as dateparser
# import os
# from sendgrid.helpers.mail import Mail, Email, To, Content
# from typing import Dict
# from IPython.display import display, Markdown
# from typing import Optional, List, Any
# load_dotenv(override=True)
# SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")

# openai_api_key = os.getenv('OPENAI_API_KEY')
# groq_api_key = os.getenv('GROQ_API_KEY')
# google_api_key = os.getenv('GOOGLE_API_KEY')

# if openai_api_key:
#     print(f"OpenAI API Key exists and begins {openai_api_key[:8]}")
# else:
#     print("OpenAI API Key not set")

# HEADERS = {"User-Agent": "FundingScraper/1.0 (research; contact: you@example.com)"}
# KEYWORDS = re.compile(r"(ph\.?d|doctoral|doctorate|masters?|m\.sc|mres|scholarship|funding|studentship|stipend)", re.I)

# @function_tool
# def find_university_domain(school: str, country: Optional[str]=None, num: int=5) -> List[str]:
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

#     search = GoogleSearch({
#         "q": query,
#         "api_key": SERPAPI_KEY,
#         "num": num
#     })
#     results = search.get_dict()
#     print(results)

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

# class SchoolAndDomain(BaseModel):
#     school: str
#     "The name of the school"
#     domain: str
#     "The school's official domain"

# search_agent_instructions = """You are a university domain research assistant. 


# FOLLOW THESE RULES:
# 1. FIRST, check if specific school names are EXPLICITLY mentioned in the query
# 2. IF explicit schools are mentioned:
#    - Return ONLY those explicitly mentioned schools and their domains
#    - Do NOT add any other schools
# 3. IF NO explicit schools are mentioned:
#    - Search for relevant schools based on the query context
#    - Return the most relevant schools and their domains

# Examples:
# - "Find MIT and Stanford domains" → Return: MIT, Stanford (only explicit)
# - "University of Toronto website" → Return: University of Toronto (only explicit)
# - "Top AI PhD programs" → Return: List of relevant schools (no explicit ones)
# - "Machine learning scholarships in UK" → Return: List of relevant UK schools"""

# class MultipleSchoolsAndDomains(BaseModel):
#     schools: List[SchoolAndDomain]
#     "List of schools and their domains"
#     search_type: str
#     "Either 'explicit' (schools were explicitly mentioned) or 'searched' (schools were found via search)"

# search_agent = Agent(
#     name="Smart university domain finder",
#     instructions=search_agent_instructions,
#     tools=[find_university_domain],
#     model="gpt-4o-mini",
#     output_type=MultipleSchoolsAndDomains
# )

# search_agent_tool = search_agent.as_tool(
#     tool_name="university_domain_search",
#     tool_description="Find university domains for given schools or research topics"
# )

# def remove_duplicate_schools(schools_list: List[SchoolAndDomain]) -> List[SchoolAndDomain]:
#     """Remove duplicate schools from the list"""
#     seen = set()
#     unique_schools = []
    
#     for school_domain in schools_list:
#         # Normalize school name for comparison
#         normalized_name = school_domain.school.lower().strip()
        
#         if normalized_name not in seen:
#             seen.add(normalized_name)
#             unique_schools.append(school_domain)
#         else:
#             print(f"Skipped duplicate: {school_domain.school}")
    
#     return unique_schools

# class KeywordSuggestion(BaseModel):
#     primary_keywords: List[str]
#     secondary_keywords: List[str]
#     search_strategy: str
#     content_types: List[str]

# keyword_agent_instructions = """You are a search strategy expert. Analyze the user's query and suggest the most effective keywords for web crawling."""

# keyword_agent = Agent(
#     name="Keyword Strategy Agent",
#     instructions=keyword_agent_instructions,
#     model="gpt-4o-mini",
#     output_type=KeywordSuggestion
# )

# # Make sure you have the keyword tool defined
# @function_tool
# async def get_search_keywords(query: str) -> Dict[str, Any]:
#     """
#     Analyze user query and return optimized keywords for web crawling.
#     """
#     keyword_result = await Runner.run(keyword_agent, query)
#     keywords = keyword_result.final_output
    
#     return {
#         "primary_keywords": keywords.primary_keywords,
#         "secondary_keywords": keywords.secondary_keywords,
#         "search_strategy": keywords.search_strategy,
#         "content_types": keywords.content_types
#     }

# # --- Utilities ---
# def polite_get(url, timeout=15):
#     try:
#         r = requests.get(url, headers=HEADERS, timeout=timeout)
#         if r.ok and "text/html" in r.headers.get("content-type", ""):
#             return r.text
#     except Exception:
#         return None
#     return None

# def extract_links(html, base_url):
#     soup = BeautifulSoup(html, "lxml")
#     base = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(base_url))
#     links = []
#     for a in soup.find_all("a", href=True):
#         href = a["href"].strip()
#         if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
#             continue
#         absolute = urljoin(base, href)
#         if urlparse(absolute).netloc.endswith(urlparse(base).netloc):
#             links.append(absolute)
#     return list(set(links))

# def extract_relevant_text(html):
#     soup = BeautifulSoup(html, "lxml")
#     text = soup.get_text(separator="\n", strip=True)
#     return text

# @function_tool
# def crawl_university_funding(domain_url: str, max_pages: int = 20) -> List[Dict[str, str]]:
#     """
#     Your original crawler - use this one with the keyword tool integration.
#     """
#     # Keywords for funding-related pages and links
#     FUNDING_KEYWORDS = re.compile(
#         r"(ph\.?d|doctoral|doctorate|masters?|m\.sc|funding|scholarship|studentship|stipend|bursary|grant|financial aid|tuition|fee|finance|money support|aid)",
#         re.I
#     )
    
#     # Keywords in URLs that indicate funding pages
#     FUNDING_URL_PATTERNS = [
#         '/funding/', '/scholarship/', '/financial-aid/', '/bursary/', 
#         '/studentship/', '/fees-funding/', '/finance/', '/grants/',
#         '/funding-opportunities/', '/scholarships/', '/financialsupport/'
#     ]
    
#     visited, to_visit, results = set(), {domain_url}, []
    
#     while to_visit and len(visited) < max_pages:
#         url = to_visit.pop()
#         if url in visited:
#             continue
#         visited.add(url)
        
#         time.sleep(1)  # Be polite
#         html = polite_get(url)
#         if not html:
#             continue
        
#         # Extract all links from the page
#         soup = BeautifulSoup(html, "lxml")
#         text = soup.get_text(separator="\n", strip=True)
        
#         # Check if this page itself is about funding
#         is_funding_page = FUNDING_KEYWORDS.search(text)
        
#         # Also check if URL suggests it's a funding page
#         url_suggests_funding = any(pattern in url.lower() for pattern in FUNDING_URL_PATTERNS)
        
#         if is_funding_page or url_suggests_funding:
#             results.append({
#                 "url": url, 
#                 "text": text[:5000],
#                 "title": soup.title.string if soup.title else "No title",
#                 "page_type": "funding_page"
#             })
        
#         # Extract and prioritize funding-related links
#         all_links = extract_links(html, url)
#         funding_links = []
#         regular_links = []
        
#         for link in all_links:
#             # Check if link text or URL suggests funding
#             link_text = ""
#             a_tag = soup.find('a', href=link.replace(domain_url, '').lstrip('/'))
#             if a_tag:
#                 link_text = a_tag.get_text(strip=True)
            
#             link_lower = link.lower()
#             is_funding_link = (
#                 FUNDING_KEYWORDS.search(link_text) or
#                 any(pattern in link_lower for pattern in FUNDING_URL_PATTERNS) or
#                 FUNDING_KEYWORDS.search(link)
#             )
            
#             if is_funding_link:
#                 funding_links.append(link)
#             else:
#                 regular_links.append(link)
        
#         # Add funding links first (higher priority)
#         for link in funding_links:
#             if link not in visited and link not in to_visit:
#                 to_visit.add(link)
        
#         # Then add regular links
#         for link in regular_links[:10]:  # Limit regular links to avoid crawling too much
#             if link not in visited and link not in to_visit:
#                 to_visit.add(link)
    
#     print(f"✅ Crawled {len(visited)} pages, found {len(results)} funding pages")
#     return results

# # Navigator Agent
# navigator_instructions = """You are a research navigator that coordinates between different research tools.

# DECISION PROCESS:
# 1. Use get_search_keywords to understand the optimal search strategy
# 2. Use university_domain_search to find relevant university domains
# 3. Use crawl_university_funding to search for funding opportunities on those domains

# The keyword analysis helps you focus on what matters most to the user."""

# class FundingPage(BaseModel):
#     url: str
#     title: str
#     preview: str

# class UniversityResult(BaseModel):
#     school: str
#     domain: str
#     funding_pages: List[FundingPage]

# class NavigationResult(BaseModel):
#     universities: List[UniversityResult]
#     search_strategy: str
#     total_funding_pages: int
#     keyword_analysis: Optional[Dict[str, Any]]

# navigator_agent = Agent(
#     name="Research Navigator",
#     instructions=navigator_instructions,
#     tools=[get_search_keywords, search_agent_tool, crawl_university_funding],
#     model="gpt-4o-mini",
#     output_type=NavigationResult
# )

# if __name__ == "__main__":
#     query = "Find PhD machine learning funding opportunities at University of Exeter and university of hertfordshire in United Kingdom"
    
#     with trace("Comprehensive Search"):
#         print("searching...")
#         print(f"searching: {query}")
        
#         # Use navigator agent directly - it will handle both domain search AND funding crawl
#         navigator_result = await Runner.run(navigator_agent, query, max_turns=25)
        
#         print(f"\n=== NAVIGATOR RESULTS ===")
#         print(f"Search strategy: {navigator_result.final_output.search_strategy}")
#         print(f"Universities found: {len(navigator_result.final_output.universities)}")
#         print(f"Total funding pages: {navigator_result.final_output.total_funding_pages}")
        
#         for uni in navigator_result.final_output.universities:
#             print(f"\n🎓 {uni.school}")
#             print(f"   🌐 {uni.domain}")
#             print(f"   📚 Funding pages: {len(uni.funding_pages)}")
            
#             for page in uni.funding_pages[:10]:  # Show first 3 pages
#                 print(f"      • {page.title}")
#                 print(f"        {page.url}")