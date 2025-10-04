import os
import re
import time
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from serpapi.google_search import GoogleSearch
from openai import OpenAI
from dotenv import load_dotenv
load_dotenv(override=True)
# --- Config ---
SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")
print(SERPAPI_KEY)
OPENAI_KEY = os.getenv("OPENAI_API_KEY")
print(OPENAI_KEY)
client = OpenAI(api_key=OPENAI_KEY)

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

# --- Step 1: Search with SerpAPI ---
def find_university_domain(school, country=None, num=5):
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

# --- Step 2: Crawl website for Masters/PhD funding ---
def crawl_for_funding(domain_url, max_pages=20):
    visited, to_visit, results = set(), {domain_url}, []
    while to_visit and len(visited) < max_pages:
        url = to_visit.pop()
        if url in visited:
            continue
        visited.add(url)

        time.sleep(1)
        html = polite_get(url)
        if not html:
            continue
        text = extract_relevant_text(html)

        # Match only pages with PhD/Masters funding info
        if KEYWORDS.search(text):
            results.append({"url": url, "text": text[:5000]})  # limit text for efficiency

        # Add new links
        to_visit.update(extract_links(html, url))

    return results

# --- Step 3: Summarize & Structure with OpenAI ---
def summarize_with_openai(pages):
    structured_results = []
    for p in pages:
        prompt = f"""
        You are an academic funding extraction assistant.
        Extract scholarship/funding details ONLY for Masters or PhD students from the text below.

        Return JSON with fields:
        - title (if mentioned)
        - degree_level (Masters, PhD, or Both)
        - amount (if mentioned, else null)
        - deadline (if mentioned, else null)
        - eligibility (short summary)
        - application_link (if available)
        - source_url

        Text:
        {p["text"]}
        """

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )

        try:
            structured_results.append({
                "source_url": p["url"],
                "info": resp.choices[0].message.content
            })
        except Exception as e:
            structured_results.append({
                "source_url": p["url"],
                "error": str(e)
            })
    return structured_results

# --- Orchestrator ---
def search_and_extract(school, country=None, max_pages=20):
    domains = find_university_domain(school, country)
    if not domains:
        return {"error": "No domain found"}
    
    results = []
    for d in domains:
        pages = crawl_for_funding(d, max_pages=max_pages)
        summaries = summarize_with_openai(pages)
        results.extend(summaries)
    
    return results

# --- Example run ---
if __name__ == "__main__":
    school = "machine learning funding for phd students in univfersity of exeter"
    country = "United Kingdom"
    data = search_and_extract(school, country, max_pages=10)

    import json
    print(json.dumps(data, indent=2))
