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
                "output": "json",
            },
            timeout=30.0,
        )
        response.raise_for_status()
        
        data = response.json()
        
        # Parse logic: Look for 'queryresult' -> 'pods' -> 'primary=true' or 'id=Result'
        try:
            query_result = data.get("queryresult", {})
            if not query_result.get("success"):
                return "Wolfram Alpha could not understand the query."
            
            pods = query_result.get("pods", [])
            
            # 1. Try to find primary pod
            result_pod = next((p for p in pods if p.get("primary")), None)
            
            # 2. Fallback to 'Result' pod
            if not result_pod:
                result_pod = next((p for p in pods if p.get("id") == "Result"), None)
                
            # 3. Fallback to first pod that is not Input
            if not result_pod and pods:
                result_pod = next((p for p in pods if p.get("id") != "Input"), pods[0])
                
            if result_pod:
                subpods = result_pod.get("subpods", [])
                if subpods:
                    return subpods[0].get("plaintext", "No text result found.")
            
            return "No result found."
            
        except Exception as e:
            return f"Error parsing Wolfram result: {str(e)}"
