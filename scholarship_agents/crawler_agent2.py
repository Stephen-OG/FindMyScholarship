from agents import Agent,AgentOutputSchema,function_tool
from openai import OpenAI
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
from typing import Optional, List
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
client = OpenAI()

@function_tool
def get_webpage_content(url: str) -> str:
    """Fetch webpage content and extract main text content"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
            
        # Get text content
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text[:8000]  # Limit to avoid token limits
        
    except Exception as e:
        return f"Error fetching {url}: {str(e)}"

# New agent that uses GPT to analyze web content
web_analyzer_instructions = """You are a web content analyzer that extracts funding information from university websites.

PROCESS:
1. Get the content of university/universities websites
2. Analyze the content to find funding opportunities, scholarships, financial aid based on user prompt
3. Extract structured information about funding options
4. Return comprehensive funding analysis

Look for keywords: scholarship, financial aid, funding, grant, bursary, tuition, assistance"""

class FundingOpportunity(BaseModel):
    title: str
    description: str
    eligibility: str
    amount: str
    deadline: str
    url: str

class UniversityFundingAnalysis(BaseModel):
    university: str
    domain: str
    funding_opportunities: List[FundingOpportunity]
    summary: str

client.chat.completions.create(
    name="Web Content Funding Analyzer",
    instructions=web_analyzer_instructions,
    tools=[get_webpage_content],
    model="gpt-4o",  # Use more capable model for analysis
    output_type=AgentOutputSchema(UniversityFundingAnalysis, strict_json_schema=False)
)