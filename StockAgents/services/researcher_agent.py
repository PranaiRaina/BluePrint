"""
Researcher Agent - Market Intelligence Sub-Agent

Uses Tavily for market search and news analysis.
Persona: Insightful, contextual, news-focused.

PRIVACY: Only market-related queries are passed to Tavily.
"""
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from openai import AsyncOpenAI
from StockAgents.core.config import settings
from StockAgents.core.prompts import RESEARCHER_SYSTEM_PROMPT

# Thread pool for blocking Tavily calls
executor = ThreadPoolExecutor(max_workers=3)

# LLM Client (Gemini via OpenAI SDK)
llm_client = AsyncOpenAI(
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    api_key=settings.GOOGLE_API_KEY
)
RESEARCHER_MODEL = "gemini-2.0-flash"  # Fast inference



async def researcher_agent(query: str) -> dict:
    """
    The Researcher Agent - Market intelligence using Tavily.
    
    Args:
        query: Market-related question to research
        
    Returns:
        {analysis: str, search_results: dict}
    """
    from StockAgents.tools.tavily_tool import tavily_market_search
    
    # Step 1: Perform market search (in executor - blocking)
    loop = asyncio.get_running_loop()
    search_results = await loop.run_in_executor(executor, tavily_market_search, query)
    
    # Step 2: Generate analysis with LLM
    messages = [
        {"role": "system", "content": RESEARCHER_SYSTEM_PROMPT},
        {"role": "user", "content": f"Question: {query}\n\nSearch Results:\n{json.dumps(search_results, indent=2)}"}
    ]
    
    try:
        response = await llm_client.chat.completions.create(
            model=RESEARCHER_MODEL,
            messages=messages,
            temperature=0.5,
            max_tokens=400
        )
        analysis = response.choices[0].message.content
    except Exception as e:
        analysis = f"Research analysis error: {str(e)}"
    
    return {
        "analysis": analysis,
        "search_results": search_results,
        "source": "researcher_agent"
    }
