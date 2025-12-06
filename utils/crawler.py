import asyncio
import os
import re
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin, urlparse

import aiohttp
from agents import function_tool
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import AsyncOpenAI

from utils.logger import logger

load_dotenv()
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

HEADERS = {"User-Agent": "FundingScraper/1.0 (research; contact: you@example.com)"}

# Base funding keywords
BASE_FUNDING_KEYWORDS = [
    r"ph\.?d", r"doctoral", r"doctorate", r"masters?", r"m\.sc",
    r"funding", r"scholarship", r"studentship", r"stipend",
    r"bursary", r"grant", r"financial aid", r"tuition",
    r"fee", r"finance", r"money support", r"aid"
]

FUNDING_URL_PATTERNS = [
    "/funding/", "/scholarship/", "/financial-aid/", "/bursary/",
    "/studentship/", "/fees-funding/", "/finance/", "/grants/",
    "/funding-opportunities/", "/scholarships/", "/financialsupport/",
]


# ----------------------------
# Keyword Extraction
# ----------------------------
async def extract_keywords_from_query(query: str) -> List[str]:
    """
    Extract relevant academic keywords from user query using AI
    
    Args:
        query: User's search query
    
    Returns:
        List of lowercase keywords to prioritize in crawling
    """
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system", 
                    "content": "Extract academic field keywords, degree levels, and funding-related terms from the query. Return as a JSON array of lowercase keywords suitable for URL/text matching."
                },
                {
                    "role": "user", 
                    "content": f"""Query: {query}

Extract ALL relevant keywords including:
- Field of study (ANY academic discipline: STEM, humanities, social sciences, arts, etc.)
  Examples: 'machine-learning', 'renaissance-history', 'organic-chemistry', 'public-policy'
- Degree level (e.g., 'phd', 'doctoral', 'masters', 'undergraduate')
- Geographic/status terms (e.g., 'international', 'european', 'domestic')
- Funding-specific terms (e.g., 'full-funding', 'tuition-waiver', 'stipend')

Be comprehensive - include all academic terms, even interdisciplinary ones.

Return format: {{"keywords": ["keyword1", "keyword2", ...]}}"""
                }
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        import json
        result = json.loads(response.choices[0].message.content)
        keywords = result.get('keywords', [])
    except Exception as e:
        print(f"⚠️  Keyword extraction failed: {e}, using fallback")
        keywords = []
    
    # Fallback extraction using regex
    query_lower = query.lower()
    
    # Extract degree levels
    if any(word in query_lower for word in ['phd', 'doctoral', 'doctorate']):
        keywords.extend(['phd', 'doctoral', 'doctorate'])
    if any(word in query_lower for word in ['master', "master's", 'msc', 'm.sc']):
        keywords.extend(['masters', 'master', 'msc'])
    if any(word in query_lower for word in ['undergraduate', 'bachelor', 'bachelors']):
        keywords.extend(['undergraduate', 'bachelor'])
    
    # Extract location/status keywords
    if 'international' in query_lower:
        keywords.append('international')
    if any(word in query_lower for word in ['europe', 'european', 'eu']):
        keywords.extend(['europe', 'european'])
    
    # Deduplicate and clean
    keywords = list(set(k.lower().strip() for k in keywords if k))
    
    return keywords


def create_dynamic_keyword_pattern(custom_keywords: List[str]) -> re.Pattern:
    """Create a regex pattern combining base and custom keywords"""
    all_keywords = BASE_FUNDING_KEYWORDS + [re.escape(kw) for kw in custom_keywords]
    pattern = r"(" + r"|".join(all_keywords) + r")"
    return re.compile(pattern, re.I)


# ----------------------------
# Async Utilities
# ----------------------------
async def fetch(session: aiohttp.ClientSession, url: str, timeout: int = 15):
    """Fetch a single URL"""
    try:
        async with session.get(url, headers=HEADERS, timeout=timeout) as r:
            if r.status == 200 and "text/html" in r.headers.get("content-type", ""):
                return await r.text()
    except Exception:
        return None
    return None


def extract_links(html: str, base_url: str) -> List[str]:
    """Extract all internal links from HTML"""
    soup = BeautifulSoup(html, "lxml")
    base = "{uri.scheme}://{uri.netloc}".format(uri=urlparse(base_url))
    links = []
    
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        absolute = urljoin(base, href)
        if urlparse(absolute).netloc.endswith(urlparse(base).netloc):
            links.append(absolute)
    
    return list(set(links))


def is_funding_relevant(
    url: str, 
    text: str, 
    keyword_pattern: re.Pattern,
    custom_keywords: List[str]
) -> tuple[bool, int]:
    """
    Determine if page is funding-related and calculate relevance score
    
    Returns:
        (is_relevant, relevance_score)
    """
    # URL check
    url_suggests_funding = any(pattern in url.lower() for pattern in FUNDING_URL_PATTERNS)
    url_has_custom = any(kw in url.lower() for kw in custom_keywords)
    
    # Text check
    text_matches_funding = bool(keyword_pattern.search(text))
    
    # Calculate relevance score
    score = 0
    if url_suggests_funding:
        score += 10
    if url_has_custom:
        score += 5
    if text_matches_funding:
        score += 3
    
    # Count custom keyword occurrences
    for kw in custom_keywords:
        score += text.lower().count(kw) * 2
    
    is_relevant = score >= 3  # Threshold for relevance
    
    return is_relevant, score


@function_tool
async def crawl_university_funding(
    domain_url: str, 
    user_query: Optional[str] = None,
    max_pages: int = 100,
    max_results: int = 40,  # Return up to 40 results
    min_relevance_score: int = 5 # Minimum score threshold
) -> List[Dict[str, str]]:
    """..."""
    
    custom_keywords = []
    if user_query:
        custom_keywords = await extract_keywords_from_query(user_query)
        print(f"🎯 Extracted keywords for {domain_url}: {', '.join(custom_keywords)}")
    
    keyword_pattern = create_dynamic_keyword_pattern(custom_keywords)
    
    visited: Set[str] = set()
    to_visit: List[tuple[str, int]] = [(domain_url, 0)]  # (url, priority_score)
    results: List[Dict[str, any]] = []
    
    async with aiohttp.ClientSession() as session:
        while to_visit and len(visited) < max_pages:
            # Sort by priority score
            to_visit.sort(key=lambda x: x[1], reverse=True)
            
            # Take top 5 URLs
            current_batch = []
            for _ in range(min(5, len(to_visit))):
                url, _ = to_visit.pop(0)
                if url not in visited:
                    current_batch.append(url)
                    visited.add(url)
            
            if not current_batch:
                break
            
            tasks = [fetch(session, url) for url in current_batch]
            pages = await asyncio.gather(*tasks)
            
            for i, html in enumerate(pages):
                url = current_batch[i]
                if not html:
                    continue
                
                soup = BeautifulSoup(html, "lxml")
                text = soup.get_text(separator="\n", strip=True)
                
                is_relevant, relevance_score = is_funding_relevant(
                    url, text, keyword_pattern, custom_keywords
                )
                
                if is_relevant:
                    results.append({
                        "url": url,
                        "title": soup.title.string if soup.title else "No title",
                        "text": text[:700],
                        "page_type": "funding_page",
                        "relevance_score": relevance_score
                    })
                
                # Extract links with priority scores
                all_links = extract_links(html, url)

                print(f"🔗 Extracted links: {all_links}")
                
                for link in all_links:
                    if link not in visited and link not in [u for u, _ in to_visit]:
                        # Calculate priority
                        priority = 0
                        
                        # High priority for funding URLs
                        if any(pattern in link.lower() for pattern in FUNDING_URL_PATTERNS):
                            priority += 100
                            
                        # Extra priority for deep funding pages
                        priority += calculate_funding_depth(link) * 20
                        
                        # Bonus for custom keywords
                        for kw in custom_keywords:
                            if kw in link.lower():
                                priority += 10
                        
                        to_visit.append((link, priority))

    # Filter by minimum relevance score
    filtered_results = [r for r in results if r.get("relevance_score", 0) >= min_relevance_score]
    
    # Sort by relevance score (highest first)
    filtered_results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    
    # Return top results up to max_results
    final_results = filtered_results[:max_results]

    # Log relevance distribution for monitoring
    tier_100_plus = len([r for r in final_results if r.get("relevance_score", 0) >= 100])
    tier_50_99 = len([r for r in final_results if 50 <= r.get("relevance_score", 0) < 100])
    tier_5_49 = len([r for r in final_results if 5 <= r.get("relevance_score", 0) < 50])
    
    logger.info(f"✅ {domain_url}: {len(final_results)} pages | "
          f"🔥 Exceptional (100+): {tier_100_plus} | "
          f"⭐ High (50-99): {tier_50_99} | "
          f"✓ Moderate (5-49): {tier_5_49}")
    
    return final_results
                        
    # print(results)
    # results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)
    # print(f"✅ Crawled {len(visited)} pages, found {len(results)} funding pages for {domain_url}")
    
    # return results


def calculate_funding_depth(url: str) -> int:
    """Count funding-related terms in URL"""
    url_lower = url.lower()
    funding_terms = ['funding', 'scholarship', 'phd', 'doctoral', 'studentship', 'financial', 'bursary']
    return sum(url_lower.count(term) for term in funding_terms)