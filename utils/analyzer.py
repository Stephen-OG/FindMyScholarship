import os

import aiohttp
from agents import function_tool
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import AsyncOpenAI

load_dotenv(override=True)
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))



@function_tool
async def analyze_funding_page(url: str, title: str, preview: str, user_query: str) -> dict:
    """
    Fetch and analyze a funding page to extract structured information.
    
    Args:
        url: Page URL to fetch and analyze
        title: Page title
        preview: Short preview of page content (500 chars)
        user_query: User's original query for context
    
    Returns:
        Structured funding information
    """
    
    # Fetch full page content
    print(f"📄 Analyzing: {url}")
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(
                url, 
                headers={"User-Agent": "FundingScraper/1.0"},
                timeout=15
            ) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, "lxml")
                    
                    # Remove scripts and styles
                    for element in soup(["script", "style", "nav", "footer", "header"]):
                        element.decompose()
                    
                    # Get main content
                    full_text = soup.get_text(separator="\n", strip=True)
                    # Limit to reasonable size (10k chars = ~2500 tokens)
                    full_text = full_text[:10000]
                else:
                    print(f"⚠️  Failed to fetch {url}, using preview only")
                    full_text = preview
        except Exception as e:
            print(f"⚠️  Error fetching {url}: {e}, using preview only")
            full_text = preview
    
    analysis_prompt = f"""Analyze this university funding page and extract key information.

USER'S QUERY: {user_query}

PAGE DETAILS:
URL: {url}
Title: {title}

CONTENT:
{full_text}

Extract the following if present (use "Not specified" if information is missing):
1. Funding opportunities mentioned (name each one)
2. Degree level (PhD, Masters, Undergraduate, etc.)
3. Field/discipline (if specific)
4. Eligibility requirements
5. Funding amount or type (full funding, tuition only, stipend amount, etc.)
6. Application deadline (if mentioned)
7. Whether it's for international students, UK/EU students, or both
8. How to apply (brief description or "See page for details")

Be specific and extract actual details from the page. If the page lists multiple opportunities, list them all.

Return as JSON with this structure:
{{
  "opportunities": [
    {{
      "name": "Name of scholarship/funding",
      "degree_level": "PhD/Masters/etc",
      "field": "Subject area",
      "eligibility": "Who can apply",
      "amount": "Funding amount/type",
      "deadline": "Application deadline",
      "for_international": true/false,
      "application_process": "How to apply"
    }}
  ],
  "page_summary": "Brief 1-2 sentence summary of what this page offers",
  "relevance_to_query": "How relevant is this to the user's needs (High/Medium/Low)"
}}"""

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a funding information extraction expert. Extract precise, structured information from scholarship pages."
            },
            {
                "role": "user",
                "content": analysis_prompt
            }
        ],
        response_format={"type": "json_object"},
        temperature=0.3
    )
    
    import json
    return json.loads(response.choices[0].message.content)