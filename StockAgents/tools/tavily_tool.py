"""
Tavily Tool - Market Intelligence Search

PRIVACY BOUNDARY: This tool sends data to an external API.
- Never pass PII (names, account numbers, etc.)
- Only pass general market queries
"""
import os
from dotenv import load_dotenv

load_dotenv()

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")

# Initialize client
try:
    from tavily import TavilyClient
    tavily_client = TavilyClient(api_key=TAVILY_API_KEY) if TAVILY_API_KEY else None
except ImportError:
    tavily_client = None

def tavily_market_search(query: str) -> dict:
    """
    Searches for market intelligence using Tavily.
    
    Args:
        query: Market-related search query (NO PII!)
    
    Returns:
        dict with search results
    """
    if not tavily_client:
        return {"error": "Tavily client not configured", "query": query}
    
    try:
        # Advanced search for better results
        response = tavily_client.search(
            query=query,
            search_depth="advanced",
            max_results=5
        )
        
        # Extract key information
        results = []
        for result in response.get("results", []):
            results.append({
                "title": result.get("title"),
                "content": result.get("content", "")[:500],  # Truncate
                "url": result.get("url")
            })
        
        return {
            "query": query,
            "results": results,
            "source": "tavily"
        }
        
    except Exception as e:
        return {"error": f"Tavily error: {str(e)}", "query": query}
