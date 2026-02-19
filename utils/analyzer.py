import json
import os
from typing import Any, Dict, List

import aiohttp
from agents import function_tool
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import AsyncOpenAI

from utils.logger import logger

load_dotenv(override=True)

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Maximum pages to analyze in a single batch (to stay within token limits)
MAX_PAGES_PER_BATCH = 5

@function_tool
async def analyze_funding_page(
    url: str, 
    title: str, 
    preview: str, 
    user_query: str,
    full_text: str = None
) -> dict:
    """
    Analyze a funding page to extract structured information.
    
    CRITICAL: Always provide full_text parameter from crawler results to avoid refetching the URL.
    The crawler already fetches and cleans the page content, so passing full_text is much faster.
    
    Args:
        url: Page URL
        title: Page title
        preview: Short preview of page content (for display)
        user_query: User's original query for context
        full_text: REQUIRED - Full page text content from crawler results (avoids refetching URL)
    
    Returns:
        Structured funding information with opportunities, eligibility, amounts, deadlines, etc.
    """
    
    logger.info(f"📄 Analyzing: {url}")
    
    # Use provided full_text if available, otherwise fetch (fallback for backward compatibility)
    if full_text is None or full_text == "":
        logger.warning(f"⚠️  No full_text provided for {url}, refetching (inefficient)")
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
                        logger.warning(f"⚠️  Failed to fetch {url}, using preview only")
                        full_text = preview
            except Exception as e:
                logger.error(f"⚠️  Error fetching {url}: {e}, using preview only")
                full_text = preview
    else:
        # Crawler already provides cleaned text, so use it directly
        # Just ensure it's within token budget (already limited in crawler, but double-check)
        full_text = full_text[:10000] if len(full_text) > 10000 else full_text
    
    analysis_prompt = f"""Analyze this university funding page and extract key information.

USER'S QUERY: {user_query}

PAGE DETAILS:
URL: {url}
Title: {title}

CONTENT:
{full_text}

CRITICAL RULES (STRICT):
1. ONLY extract funding opportunities that are explicitly present in the provided page content.
2. DO NOT invent, infer, summarize, or generalize funding opportunities.
3. DO NOT create generic or placeholder entries such as:
   - "PhD Machine Learning Funding"
   - "Machine Learning Scholarships"
   unless those exact names appear in the page content.

4. If NO relevant funding opportunities exist that match the user's query:
   - Return an empty opportunities array: []
   - In page_summary, clearly state: "No relevant funding opportunities were found."
   - DO NOT fabricate opportunities.
   - DO NOT create placeholder entries.
   - DO NOT summarize unrelated content as funding.

5. Each funding opportunity you extract MUST:
   - Exist explicitly in the provided page content
   - Be directly relevant to the user's query
   - Include factual information only
   - Never include guessed or assumed information

6. If the page contains no funding information:
   - Return opportunities: []
   - State in page_summary: "No funding information was found on this page."

Extract the following if present (use "Not specified" if information is missing):
1. Funding opportunities mentioned (name each one - use exact names from the page)
2. Degree level (PhD, Masters, Undergraduate, etc.)
3. Field/discipline (if specific)
4. Eligibility requirements
5. Funding amount or type (full funding, tuition only, stipend amount, etc.)
6. Application deadline (if mentioned)
7. Whether it's for international students, UK/EU students, or both
8. How to apply (brief description or "See page for details")

Be specific and extract actual details from the page. If the page lists multiple opportunities, list them all.

DO NOT hallucinate.
DO NOT fabricate funding.
DO NOT create placeholders.
ONLY extract real funding opportunities from the input content.

Return as JSON with this structure:
{{
  "opportunities": [
    {{
      "name": "Name of scholarship/funding (exact name from page)",
      "degree_level": "PhD/Masters/etc",
      "field": "Subject area",
      "eligibility": "Who can apply",
      "amount": "Funding amount/type",
      "deadline": "Application deadline",
      "for_international": true/false,
      "application_process": "How to apply"
    }}
  ],
  "page_summary": "Brief 1-2 sentence summary of what this page offers. If no funding found, state that clearly.",
  "relevance_to_query": "How relevant is this to the user's needs (High/Medium/Low)"
}}"""

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": "You are a funding information extraction expert. Extract ONLY real, explicitly mentioned funding opportunities from scholarship pages. DO NOT invent, infer, or fabricate funding opportunities. Only extract what is explicitly stated in the page content."
            },
            {
                "role": "user",
                "content": analysis_prompt
            }
        ],
        response_format={"type": "json_object"},
        temperature=0.3
    )
    
    return json.loads(response.choices[0].message.content)


@function_tool
async def analyze_funding_pages_batch(
    urls: List[str],
    titles: List[str],
    previews: List[str],
    full_texts: List[str],
    user_query: str,
    max_pages_per_batch: int = MAX_PAGES_PER_BATCH,
) -> List[Dict[str, Any]]:
    """
    Analyze multiple funding pages in batches to reduce API calls.
    
    This function processes multiple pages in a single API call, dramatically reducing
    the number of API calls from N (one per page) to N/max_pages_per_batch.
    
    CRITICAL: Always provide full_text for each page from crawler results to avoid refetching.
    
    Args:
        urls: List of page URLs
        titles: List of page titles (same order as urls)
        previews: List of short previews (same order as urls)
        full_texts: List of full page texts from crawler (same order as urls)
        user_query: User's original query for context
        max_pages_per_batch: Maximum pages to analyze per API call (default: 5)
    
    Returns:
        List of analysis results, one per page, each containing:
        {
            "url": str,
            "opportunities": [...],
            "page_summary": str,
            "relevance_to_query": str
        }
    """
    
    # Build internal page objects from parallel lists
    if not urls:
        logger.warning("No URLs provided to analyze_funding_pages_batch")
        return []

    n = len(urls)
    pages: List[Dict[str, Any]] = []
    for i in range(n):
        url = urls[i]
        title = titles[i] if i < len(titles) else ""
        preview = previews[i] if i < len(previews) else ""
        full_text = full_texts[i] if i < len(full_texts) else ""
        pages.append(
            {
                "url": url,
                "title": title,
                "preview": preview,
                "full_text": full_text,
            }
        )
    
    logger.info(f"📦 Batch analyzing {len(pages)} pages in batches of {max_pages_per_batch}")
    
    all_results = []
    
    # Process pages in batches
    for batch_start in range(0, len(pages), max_pages_per_batch):
        batch = pages[batch_start:batch_start + max_pages_per_batch]
        batch_num = (batch_start // max_pages_per_batch) + 1
        total_batches = (len(pages) + max_pages_per_batch - 1) // max_pages_per_batch
        
        logger.info(f"📦 Processing batch {batch_num}/{total_batches} ({len(batch)} pages)")
        
        # Build batch prompt
        pages_text = []
        for i, page in enumerate(batch, 1):
            url = page.get("url", "Unknown URL")
            title = page.get("title", "No title")
            full_text = page.get("full_text", "")
            
            if not full_text:
                logger.warning(f"⚠️  Page {i} ({url}) missing full_text, skipping from batch")
                continue
            
            # Limit each page's text to stay within token budget
            # With 5 pages, ~2000 chars per page = ~10k total = ~2500 tokens
            page_text = full_text[:2000] if len(full_text) > 2000 else full_text
            
            pages_text.append(f"""
--- PAGE {i} ---
URL: {url}
Title: {title}
Content:
{page_text}
""")
        
        if not pages_text:
            logger.warning("No valid pages in batch (all missing full_text)")
            continue
        
        batch_prompt = f"""Analyze these university funding pages and extract key information for EACH page.

USER'S QUERY: {user_query}

PAGES TO ANALYZE:
{''.join(pages_text)}

CRITICAL RULES (STRICT):
1. ONLY extract funding opportunities that are explicitly present in the provided page content.
2. DO NOT invent, infer, summarize, or generalize funding opportunities.
3. DO NOT create generic or placeholder entries such as:
   - "PhD Machine Learning Funding"
   - "Machine Learning Scholarships"
   unless those exact names appear in the page content.

4. If NO relevant funding opportunities exist that match the user's query:
   - Return an empty opportunities array: []
   - In page_summary, clearly state: "No relevant funding opportunities were found."
   - DO NOT fabricate opportunities.
   - DO NOT create placeholder entries.
   - DO NOT summarize unrelated content as funding.

5. Each funding opportunity you extract MUST:
   - Exist explicitly in the provided page content
   - Be directly relevant to the user's query
   - Include factual information only
   - Never include guessed or assumed information

6. If a page contains no funding information:
   - Return opportunities: []
   - State in page_summary: "No funding information was found on this page."

For EACH page, extract the following if present (use "Not specified" if information is missing):
1. Funding opportunities mentioned (name each one - use exact names from the page, be specific: "Graduate Research Assistantship", "Merit Scholarship", etc.)
2. Degree level (PhD, Masters, Undergraduate, etc.)
3. Field/discipline (if specific - e.g., "Data Science", "Computer Science", etc.)
4. Eligibility requirements (be specific: GPA requirements, citizenship, enrollment status, etc.)
5. Funding amount or type (be specific: "$25,000/year", "Full tuition waiver", "£18,000 stipend", etc. - avoid generic terms)
6. Application deadline (extract actual dates if mentioned)
7. Whether it's for international students, domestic students, or both
8. How to apply (specific steps, links, or "See page for details" if not specified)

EXTRACTION GUIDELINES:
- If a page mentions "financial aid" or "funding available" but doesn't specify amounts, look for links to detailed pages
- If a page is about a program/certificate, check if it mentions scholarships, assistantships, or funding specifically for that program
- Extract actual numbers, dates, and specific program names - avoid generic phrases
- If the page is not actually about funding but mentions it in passing, note that in the summary
- Be thorough - many pages list multiple funding opportunities

Be specific and extract actual details from each page. If a page lists multiple opportunities, list them all.

DO NOT hallucinate.
DO NOT fabricate funding.
DO NOT create placeholders.
ONLY extract real funding opportunities from the input content.

Return as JSON with this structure:
{{
  "pages": [
    {{
      "url": "Page URL",
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
    }}
  ]
}}

IMPORTANT: Return results for ALL {len(batch)} pages in the order they were provided."""
        
        try:
            response = await client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a funding information extraction expert. Extract ONLY real, explicitly mentioned funding opportunities from scholarship pages. DO NOT invent, infer, or fabricate funding opportunities. Only extract what is explicitly stated in the page content. If no funding is found, return empty opportunities array."
                    },
                    {
                        "role": "user",
                        "content": batch_prompt
                    }
                ],
                response_format={"type": "json_object"},
                temperature=0.3
            )
            
            result = json.loads(response.choices[0].message.content)
            
            # Extract results for each page
            batch_results = result.get("pages", [])
            
            # Ensure we have results for all pages (handle cases where LLM might skip some)
            for i, page in enumerate(batch):
                url = page.get("url", "Unknown")
                # Find matching result by URL
                page_result = next(
                    (r for r in batch_results if r.get("url") == url),
                    None
                )
                
                if page_result:
                    all_results.append(page_result)
                else:
                    # Fallback: create empty result if LLM didn't return it
                    logger.warning(f"⚠️  No result returned for {url}, creating placeholder")
                    all_results.append({
                        "url": url,
                        "opportunities": [],
                        "page_summary": "Analysis incomplete",
                        "relevance_to_query": "Unknown"
                    })
            
        except Exception as e:
            logger.error(f"❌ Error analyzing batch {batch_num}: {e}")
            # Create placeholder results for failed batch
            for page in batch:
                all_results.append({
                    "url": page.get("url", "Unknown"),
                    "opportunities": [],
                    "page_summary": f"Analysis failed: {str(e)}",
                    "relevance_to_query": "Unknown"
                })
    
    logger.info(f"✅ Batch analysis complete: {len(all_results)} pages analyzed")
    return all_results