"""Wolfram Alpha LLM API integration."""

import httpx
from CalcAgent.config.config import WOLFRAM_APP_ID, WOLFRAM_API_URL


async def query_wolfram(query: str) -> str:
    """
    Call Wolfram Alpha LLM API with a financial query.
    
    Args:
        query: Natural language query for Wolfram Alpha (e.g., "compound interest 1000 at 5% for 10 years")
    
    Returns:
        Text result from Wolfram Alpha with calculation details
    """
    async with httpx.AsyncClient() as client:
        response = await client.get(
            WOLFRAM_API_URL,
            params={
                "input": query,
                "appid": WOLFRAM_APP_ID,
                "maxchars": 2000,
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return response.text
