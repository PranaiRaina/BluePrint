import os
import json
import hashlib
from typing import Annotated
from tavily import TavilyClient

# Tavily cache configuration
TAVILY_CACHE_DIR = os.path.join(os.path.dirname(__file__), "tavily_cache")

def _get_cache_key(query: str, search_type: str) -> str:
    """Generate a cache key from query parameters."""
    key_string = f"{search_type}:{query}"
    return hashlib.md5(key_string.encode()).hexdigest()

def _get_cached_result(cache_key: str) -> dict | None:
    """Retrieve cached Tavily result if exists."""
    os.makedirs(TAVILY_CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(TAVILY_CACHE_DIR, f"{cache_key}.json")
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                return json.load(f)
        except:
            return None
    return None

def _save_to_cache(cache_key: str, result: dict) -> None:
    """Save Tavily result to cache."""
    os.makedirs(TAVILY_CACHE_DIR, exist_ok=True)
    cache_file = os.path.join(TAVILY_CACHE_DIR, f"{cache_key}.json")
    try:
        with open(cache_file, "w") as f:
            json.dump(result, f)
    except Exception as e:
        print(f"Warning: Failed to cache Tavily result: {e}")

def get_social_news(
    ticker: Annotated[str, "Ticker symbol"],
    start_date: Annotated[str, "Start date in yyyy-mm-dd format"],
    end_date: Annotated[str, "End date in yyyy-mm-dd format"],
    query: Annotated[str, "Optional specific search query for social media"] = None,
) -> str:
    """
    Retrieve social media discussions and news for a given ticker symbol using Tavily.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "Error: TAVILY_API_KEY environment variable not set."

    try:
        # Construct a query focused on social sentiment and discussions
        if query:
            final_query = f"{query} {start_date} to {end_date}"
        else:
            final_query = f"${ticker} stock social media discussions sentiment analysis {start_date} to {end_date} reddit twitter"
        
        # Check cache first
        cache_key = _get_cache_key(final_query, "social_news")
        cached = _get_cached_result(cache_key)
        if cached:
            print("DEBUG: Using cached Tavily result for social_news")
            response = cached
        else:
            tavily_client = TavilyClient(api_key=api_key)
            response = tavily_client.search(
                query=final_query,
                search_depth="advanced",
                topic="news", 
                days=3,
                max_results=5
            )
            # Save to cache
            _save_to_cache(cache_key, response)
        
        results = response.get("results", [])
        if not results:
            return f"No social media news found for {ticker} between {start_date} and {end_date}."

        formatted_results = []
        for result in results:
            title = result.get("title", "No Title")
            content = result.get("content", "No Content")
            url = result.get("url", "No URL")
            score = result.get("score", "N/A")
            published_date = result.get("published_date")

            # Strict filtering if date is available
            if published_date:
                try:
                    if published_date > end_date:
                         continue
                except:
                    pass

            formatted_results.append(f"Title: {title}\nSource: {url}\nDate: {published_date}\nRelevance: {score}\nSummary: {content}\n")

        return "\n---\n".join(formatted_results)

    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"DEBUG: Tavily get_social_news failed. Query: {final_query if 'final_query' in locals() else 'N/A'}")
        return f"Error fetching social news from Tavily: {str(e)}"

def get_global_news(
    look_back_days: int = 3,
    limit: int = 5,
    end_date: str = None,
) -> str:
    """
    Retrieve global financial market news and macroeconomic updates.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        return "Error: TAVILY_API_KEY environment variable not set."

    try:
        query = f"global financial market news macroeconomic updates {end_date}"
        
        # Check cache first
        cache_key = _get_cache_key(query, "global_news")
        cached = _get_cached_result(cache_key)
        if cached:
            print("DEBUG: Using cached Tavily result for global_news")
            response = cached
        else:
            tavily_client = TavilyClient(api_key=api_key)
            response = tavily_client.search(
                query=query,
                search_depth="advanced",
                topic="news", 
                max_results=limit
            )
            # Save to cache
            _save_to_cache(cache_key, response)
        
        results = response.get("results", [])
        if not results:
            return "No global market news found."

        formatted_results = []
        for result in results:
            title = result.get("title", "No Title")
            content = result.get("content", "No Content")
            url = result.get("url", "No URL")
            published_date = result.get("published_date")
            
            # Simple date check if possible (lexicographical for ISO)
            if end_date and published_date:
                try:
                    # Handle both string and int (timestamp) formats
                    if isinstance(published_date, int):
                        from datetime import datetime
                        published_date = datetime.fromtimestamp(published_date).strftime("%Y-%m-%d")
                    if isinstance(published_date, str) and published_date > end_date:
                        continue
                except:
                    pass  # If comparison fails, include the result anyway

            formatted_results.append(f"Title: {title}\nSource: {url}\nDate: {published_date}\nSummary: {content}\n")

        return "\n---\n".join(formatted_results)

    except Exception as e:
        return f"Error fetching global news from Tavily: {str(e)}"
