"""
Quant Agent - Risk Analysis Sub-Agent

Uses Wolfram Cloud for mathematical computations and Finnhub for analyst ratings.
Persona: Dry, numerical, focused on data.
"""
import json
import re
import asyncio
from concurrent.futures import ThreadPoolExecutor
from openai import AsyncOpenAI
from StockAgents.core.config import settings
from StockAgents.core.prompts import QUANT_SYSTEM_PROMPT
from StockAgents.tools.wolfram_tool import wolfram_risk_analysis
from StockAgents.tools.yfinance_tool import get_historical_prices
from StockAgents.services.finnhub_client import finnhub_client

# Thread pool for blocking Wolfram calls
executor = ThreadPoolExecutor(max_workers=3)

# LLM Client (Gemini via OpenAI SDK)
llm_client = AsyncOpenAI(
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    api_key=settings.GOOGLE_API_KEY
)
QUANT_MODEL = "gemini-2.0-flash"  # Fast inference



async def quant_agent(ticker: str) -> dict:
    """
    The Quant Agent - Strictly analytical, data-driven.
    Uses Wolfram for risk calculations and Finnhub for analyst ratings.
    
    Returns:
        {analysis: str, risk_data: dict}
    """
    
    
    ticker = ticker.upper().strip()
    
    # Step 1: Get historical prices (in executor - blocking)
    loop = asyncio.get_running_loop()
    history = await loop.run_in_executor(executor, get_historical_prices, ticker)
    prices = history.get("prices", []) if "error" not in history else []
    
    # Step 2: Get company metrics from Finnhub (async)
    metrics = await finnhub_client.get_company_metrics(ticker)
    
    # Step 3: Get analyst ratings from Finnhub (async)
    analyst_ratings = await finnhub_client.get_analyst_ratings(ticker)
    
    # Context enhancement for ETFs/Funds if ratings are missing
    if "error" in analyst_ratings:
        analyst_ratings["note"] = "Analyst ratings typically unavailable for ETFs/Funds. Focus on expense ratio, holdings, and technicals."
    
    # Step 4: Compute risk using Wolfram (in executor - blocking)
    risk_data = await loop.run_in_executor(
        executor, 
        wolfram_risk_analysis, 
        ticker, 
        prices, 
        metrics, 
        analyst_ratings
    )
    
    # Step 5: Generate analysis with LLM
    messages = [
        {"role": "system", "content": QUANT_SYSTEM_PROMPT},
        {"role": "user", "content": f"Analyze this risk data for {ticker}:\n\n{json.dumps(risk_data, indent=2)}"}
    ]
    
    try:
        response = await llm_client.chat.completions.create(
            model=QUANT_MODEL,
            messages=messages,
            temperature=0.3,
            max_tokens=400
        )
        analysis = response.choices[0].message.content
    except Exception as e:
        analysis = f"Quant analysis error: {str(e)}"
    
    return {
        "analysis": analysis,
        "risk_data": risk_data,
        "source": "quant_agent"
    }
