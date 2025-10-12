from agents import function_tool
import re
import time
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from typing import Dict
from typing import Optional, List, Any


HEADERS = {"User-Agent": "FundingScraper/1.0 (research; contact: you@example.com)"}
KEYWORDS = re.compile(r"(ph\.?d|doctoral|doctorate|masters?|m\.sc|mres|scholarship|funding|studentship|stipend)", re.I)

# --- Utilities ---
def polite_get(url, timeout=15):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout)
        if r.ok and "text/html" in r.headers.get("content-type", ""):
            return r.text
    except Exception:
        return None
    return None

def extract_links(html, base_url):
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

def extract_relevant_text(html):
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(separator="\n", strip=True)
    return text

@function_tool
def crawl_university_funding(domain_url: str, max_pages: int = 20) -> List[Dict[str, str]]:
    """
    Your original crawler - use this one with the keyword tool integration.
    """
    # Keywords for funding-related pages and links
    FUNDING_KEYWORDS = re.compile(
        r"(ph\.?d|doctoral|doctorate|masters?|m\.sc|funding|scholarship|studentship|stipend|bursary|grant|financial aid|tuition|fee|finance|money support|aid)",
        re.I
    )
    
    # Keywords in URLs that indicate funding pages
    FUNDING_URL_PATTERNS = [
        '/funding/', '/scholarship/', '/financial-aid/', '/bursary/', 
        '/studentship/', '/fees-funding/', '/finance/', '/grants/',
        '/funding-opportunities/', '/scholarships/', '/financialsupport/'
    ]
    
    visited, to_visit, results = set(), {domain_url}, []
    
    while to_visit and len(visited) < max_pages:
        url = to_visit.pop()
        if url in visited:
            continue
        visited.add(url)
        
        time.sleep(1)  # Be polite
        html = polite_get(url)
        if not html:
            continue

        # Extract all links from the page
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text(separator="\n", strip=True)
        
        # Check if this page itself is about funding
        is_funding_page = FUNDING_KEYWORDS.search(text)
        
        # Also check if URL suggests it's a funding page
        url_suggests_funding = any(pattern in url.lower() for pattern in FUNDING_URL_PATTERNS)
        
        if is_funding_page or url_suggests_funding:
            results.append({
                "url": url, 
                "text": text[:5000],
                "title": soup.title.string if soup.title else "No title",
                "page_type": "funding_page"
            })
        
        # Extract and prioritize funding-related links
        all_links = extract_links(html, url)
        funding_links = []
        regular_links = []

        for link in all_links:
            # Check if link text or URL suggests funding
            link_text = ""
            a_tag = soup.find('a', href=link.replace(domain_url, '').lstrip('/'))
            if a_tag:
                link_text = a_tag.get_text(strip=True)
            
            link_lower = link.lower()
            is_funding_link = (
                FUNDING_KEYWORDS.search(link_text) or
                any(pattern in link_lower for pattern in FUNDING_URL_PATTERNS) or
                FUNDING_KEYWORDS.search(link)
            )
            
            if is_funding_link:
                funding_links.append(link)
            else:
                regular_links.append(link)
        
        # Add funding links first (higher priority)
        for link in funding_links:
            if link not in visited and link not in to_visit:
                to_visit.add(link)

        # Then add regular links
        for link in regular_links[:10]:  # Limit regular links to avoid crawling too much
            if link not in visited and link not in to_visit:
                to_visit.add(link)
    
    print(f"✅ Crawled {len(visited)} pages, found {len(results)} funding pages")
    return results

