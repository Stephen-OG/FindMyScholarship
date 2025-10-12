import os
import re
import time
import asyncio
import aiohttp
import requests
import xml.etree.ElementTree as ET
from pydantic import BaseModel
from dotenv import load_dotenv
from serpapi.google_search import GoogleSearch
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
from typing import List, Dict, Any

from agents import Agent, Runner, trace, function_tool

load_dotenv(override=True)

# === Environment Keys ===
SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")
openai_api_key = os.getenv('OPENAI_API_KEY')

if openai_api_key:
    print(f"✅ OpenAI API Key loaded ({openai_api_key[:8]}...)")
else:
    print("❌ OpenAI API Key not set")

HEADERS = {"User-Agent": "FundingScraper/1.0 (research; contact: you@example.com)"}

# === Cache to prevent duplicate crawling ===
crawl_cache = {}

# === Enhanced Domain Matching ===
def get_base_domain(netloc: str) -> str:
    """Extract base domain from netloc for flexible matching"""
    parts = netloc.split('.')
    if len(parts) >= 2:
        if parts[-2] in ['ac', 'edu', 'gov'] and len(parts) > 2:
            return '.'.join(parts[-3:])
        return '.'.join(parts[-2:])
    return netloc

def is_same_domain(url1: str, url2: str) -> bool:
    """Check if two URLs belong to the same base domain"""
    domain1 = get_base_domain(urlparse(url1).netloc)
    domain2 = get_base_domain(urlparse(url2).netloc)
    return domain1 == domain2

# === Enhanced Link Extraction ===
def extract_links_enhanced(html: str, base_url: str) -> List[str]:
    """Extract links with better domain matching"""
    soup = BeautifulSoup(html, "lxml")
    base_netloc = urlparse(base_url).netloc
    base_domain = get_base_domain(base_netloc)
    
    links = set()
    
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith(('#', 'mailto:', 'tel:', 'javascript:')):
            continue
            
        absolute = urljoin(base_url, href)
        url_netloc = urlparse(absolute).netloc
        url_domain = get_base_domain(url_netloc)
        
        if url_domain == base_domain:
            links.add(absolute)
    
    return list(links)

# === Simplified Sitemap Discovery ===
async def discover_sitemaps(session: aiohttp.ClientSession, domain_url: str) -> List[str]:
    """Discover sitemaps for comprehensive link discovery"""
    sitemap_urls = []
    common_sitemaps = ['/sitemap.xml', '/sitemap_index.xml', '/robots.txt']
    
    for sitemap_path in common_sitemaps:
        sitemap_url = urljoin(domain_url, sitemap_path)
        try:
            async with session.get(sitemap_url, headers=HEADERS, timeout=5) as response:
                if response.status == 200:
                    sitemap_urls.append(sitemap_url)
                    print(f"✅ Found sitemap: {sitemap_url}")
        except:
            continue
    
    return sitemap_urls

async def parse_sitemap(session: aiohttp.ClientSession, sitemap_url: str) -> List[str]:
    """Parse sitemap and extract all URLs"""
    urls = []
    try:
        async with session.get(sitemap_url, headers=HEADERS, timeout=10) as response:
            if response.status == 200:
                content = await response.text()
                
                try:
                    root = ET.fromstring(content)
                    for url_elem in root.findall('.//{http://www.sitemaps.org/schemas/sitemap/0.9}loc'):
                        if url_elem.text:
                            urls.append(url_elem.text)
                except ET.ParseError:
                    for line in content.split('\n'):
                        line = line.strip()
                        if line and (line.startswith('http://') or line.startswith('https://')):
                            urls.append(line)
                
                print(f"📊 Sitemap provided {len(urls)} URLs")
                return urls
    except Exception as e:
        print(f"❌ Error parsing sitemap: {e}")
    
    return []

# === Enhanced Crawler ===
async def async_get(session: aiohttp.ClientSession, url: str, timeout: int = 10) -> str:
    """Asynchronous polite GET request"""
    try:
        async with session.get(url, headers=HEADERS, timeout=timeout) as response:
            if response.status == 200 and "text/html" in response.headers.get("content-type", "").lower():
                return await response.text()
    except:
        pass
    return ""

def extract_relevant_text(html: str) -> str:
    """Extract clean text from HTML"""
    if not html:
        return ""
    soup = BeautifulSoup(html, "lxml")
    for script in soup(["script", "style"]):
        script.decompose()
    return soup.get_text(separator="\n", strip=True)

def extract_title(html: str) -> str:
    """Extract title from HTML"""
    if not html:
        return "No title"
    soup = BeautifulSoup(html, "lxml")
    if soup.title and soup.title.string:
        return soup.title.string.strip()
    return "No title"

async def crawl_university_domain_async(domain_url: str, keywords: List[str], max_pages: int = 15) -> List[Dict[str, str]]:
    """Enhanced crawler with sitemap discovery"""
    # Create cache key
    cache_key = f"{domain_url}_{'_'.join(sorted(keywords))}"
    
    if cache_key in crawl_cache:
        print(f"✅ Using cached results for {domain_url}")
        return crawl_cache[cache_key]
    
    keyword_pattern = re.compile("|".join(map(re.escape, keywords)), re.I)
    visited, to_visit, results = set(), {domain_url}, []
    
    async with aiohttp.ClientSession() as session:
        print(f"🔍 Starting crawl for {domain_url}")
        
        # Step 1: Discover sitemaps
        sitemap_urls = await discover_sitemaps(session, domain_url)
        for sitemap_url in sitemap_urls:
            sitemap_links = await parse_sitemap(session, sitemap_url)
            for link in sitemap_links[:10]:  # Limit sitemap links
                if link not in visited and link not in to_visit:
                    to_visit.add(link)
        
        # Step 2: Crawl
        while to_visit and len(visited) < max_pages:
            current_url = to_visit.pop()
            if current_url in visited:
                continue
                
            visited.add(current_url)
            html = await async_get(session, current_url)
            
            if not html:
                continue
                
            text = extract_relevant_text(html)
            title = extract_title(html)
            
            # Check if page is relevant
            if keyword_pattern.search(text) or any(k.lower() in current_url.lower() for k in keywords):
                results.append({
                    "url": current_url, 
                    "title": title,
                    "preview": text[:200] + "..." if len(text) > 200 else text
                })
                print(f"✅ Funding page: {title}")

            # Extract new links
            new_links = extract_links_enhanced(html, current_url)
            for link in new_links[:5]:  # Limit new links per page
                if link not in visited and link not in to_visit:
                    to_visit.add(link)

            await asyncio.sleep(0.5)
    
    print(f"📊 Crawl completed: {len(results)} funding pages found")
    
    # Convert to simple format
    funding_pages = []
    for result in results:
        funding_pages.append({
            "url": result["url"],
            "title": result["title"],
            "preview": result["preview"]
        })
    
    crawl_cache[cache_key] = funding_pages
    return funding_pages

# === Direct Approach - No Complex Agent Coordination ===
@function_tool
async def search_university_funding(query: str) -> Dict[str, Any]:
    """
    Direct funding search tool that handles everything in one call.
    Extracts universities, finds domains, generates keywords, and crawls.
    """
    print(f"🎯 Starting funding search for: {query}")
    
    # Step 1: Extract university names from query
    university_keywords = ["university", "college", "institute"]
    words = query.lower().split()
    universities = []
    
    i = 0
    while i < len(words):
        if words[i] in university_keywords and i > 0:
            # Get the university name (usually 1-3 words before "university")
            name_parts = []
            for j in range(max(0, i-2), i+1):
                if j < len(words):
                    name_parts.append(words[j])
            university_name = " ".join(name_parts).title()
            universities.append(university_name)
        i += 1
    
    # Fallback: look for capitalized words that might be university names
    if not universities:
        potential_universities = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\s+University\b', query)
        universities = list(set(potential_universities))
    
    # If still no universities found, use defaults
    if not universities:
        universities = ["University of Exeter", "University of Oxford"]
    
    print(f"🎓 Found universities: {universities}")
    
    # Step 2: Find domains for each university
    university_domains = {}
    for university in universities:
        print(f"🔍 Searching domain for: {university}")
        
        search = GoogleSearch({
            "q": f"{university} official site",
            "api_key": SERPAPI_KEY,
            "num": 3
        })
        results = search.get_dict()
        
        if "organic_results" in results:
            for r in results["organic_results"]:
                if "link" in r:
                    url = r["link"]
                    netloc = urlparse(url).netloc.lower()
                    if any(x in netloc for x in ["univ", "edu", "ac."]):
                        university_domains[university] = url
                        print(f"✅ Domain for {university}: {url}")
                        break
        
        # If no domain found, use a default
        if university not in university_domains:
            # Create a plausible default domain
            domain_name = university.lower().replace(" ", "").replace("of", "") + ".edu"
            university_domains[university] = f"https://www.{domain_name}"
            print(f"⚠️  Using default domain for {university}: {university_domains[university]}")
    
    # Step 3: Generate keywords
    funding_keywords = ["phd", "doctoral", "funding", "scholarship", "studentship", "stipend", "financial aid"]
    query_keywords = re.findall(r'\b\w+\b', query.lower())
    
    relevant_keywords = [kw for kw in query_keywords if kw in funding_keywords or len(kw) > 5]
    
    if not relevant_keywords:
        relevant_keywords = ["phd", "funding", "scholarship"]
    
    keywords = list(set(relevant_keywords + funding_keywords))[:6]
    print(f"🔑 Using keywords: {keywords}")
    
    # Step 4: Crawl each university domain
    all_results = []
    total_pages = 0
    
    for university, domain in university_domains.items():
        print(f"🚀 Crawling {university} at {domain}")
        
        try:
            funding_pages = await crawl_university_domain_async(domain, keywords, max_pages=10)
            all_results.append({
                "school": university,
                "domain": domain,
                "funding_pages": funding_pages
            })
            total_pages += len(funding_pages)
            print(f"✅ {university}: {len(funding_pages)} funding pages found")
        except Exception as e:
            print(f"❌ Error crawling {university}: {e}")
            all_results.append({
                "school": university,
                "domain": domain,
                "funding_pages": []
            })
    
    # Return final results
    result = {
        "universities": all_results,
        "total_pages": total_pages,
        "search_strategy": f"Enhanced crawl with keywords: {', '.join(keywords)}"
    }
    
    print(f"🎉 Search completed: {total_pages} total funding pages found across {len(universities)} universities")
    return result

# === Simple Agent that just uses the all-in-one tool ===
class SimpleFundingResult(BaseModel):
    universities: List[Dict[str, Any]]
    total_pages: int
    search_strategy: str

simple_agent_instructions = """
You are a university funding search assistant. 
When given a query about university funding, use the search_university_funding tool.
Return the results exactly as provided by the tool.
"""

simple_agent = Agent(
    name="Simple Funding Searcher",
    instructions=simple_agent_instructions,
    tools=[search_university_funding],
    model="gpt-4o-mini",
    output_type=SimpleFundingResult
)

# === Main Execution ===
async def main():
    query = "Find PhD machine learning funding opportunities at University of Exeter and University of Oxford"
    
    print("=" * 60)
    print("🎓 UNIVERSITY FUNDING SEARCHER")
    print("=" * 60)
    print(f"Query: {query}")
    print("=" * 60)

    try:
        with trace("Funding Search"):
            print(f"\n🔍 Starting search...")
            
            # Use the simple agent with just one tool
            result = await Runner.run(simple_agent, query, max_turns=3)
            
            if not result or not result.final_output:
                print("❌ No results found")
                return

            output = result.final_output
            
            print(f"\n" + "=" * 60)
            print("📊 FINAL RESULTS")
            print("=" * 60)
            print(f"Search strategy: {output.search_strategy}")
            print(f"Universities processed: {len(output.universities)}")
            print(f"Total funding pages: {output.total_pages}")
            print("=" * 60)

            for uni in output.universities:
                print(f"\n🎓 {uni['school']}")
                print(f"   🌐 {uni['domain']}")
                print(f"   📚 Funding pages: {len(uni['funding_pages'])}")
                
                if uni['funding_pages']:
                    for i, page in enumerate(uni['funding_pages'][:5], 1):
                        print(f"      {i}. {page['title']}")
                        print(f"         🔗 {page['url']}")
                        if page['preview']:
                            print(f"         📝 {page['preview'][:100]}...")
                        print()
                else:
                    print("      No funding pages found")
                    
    except Exception as e:
        print(f"❌ Error occurred: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Clear cache and run
    crawl_cache.clear()
    asyncio.run(main())