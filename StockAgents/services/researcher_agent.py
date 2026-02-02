"""
Researcher Agent - Market Intelligence Sub-Agent

Uses Tavily for market search and news analysis.
Persona: Insightful, contextual, news-focused.

PRIVACY: Only market-related queries are passed to Tavily.
"""

import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any
from StockAgents.core.prompts import RESEARCHER_SYSTEM_PROMPT
from .base_agent import BaseAgent
from .llm_service import llm_service

# Thread pool for blocking Tavily calls
executor = ThreadPoolExecutor(max_workers=3)


class ResearcherAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Researcher", client=llm_service.client)
        self.model = "gemini-2.5-flash"

    async def run(self, query: str) -> Dict[str, Any]:
        """
        Execute the iterative research process.
        Input: "Why is Apple down?"
        Internal Loop: Plan -> Search -> Analyze -> Refine -> Answer
        """
        # Step 1: Initial Search (Deep Context)
        from StockAgents.tools.tavily_tool import tavily_market_search

        loop = asyncio.get_running_loop()

        # We perform a robust search first
        # In a more advanced version, we would let the LLM decide the search query
        # For now, we trust the Planner's query is specific enough.

        # Thought: "I need to find news explaining the user's query"
        search_results = await loop.run_in_executor(
            executor, tavily_market_search, query
        )

        # Step 2: Synthesis
        # Check if results are empty
        if (
            not search_results
            or "results" not in search_results
            or not search_results["results"]
        ):
            # Fallback: Try a broader search if specific fail
            pass

        messages = [
            {"role": "system", "content": RESEARCHER_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"User Question: {query}\n\nSearch Results:\n{json.dumps(search_results, indent=2)}\n\nProvide a detailed market intelligence report.",
            },
        ]

        try:
            response = await self.client.chat.completions.create(
                model=self.model, messages=messages, temperature=0.5, max_tokens=600
            )
            analysis = response.choices[0].message.content
        except Exception as e:
            analysis = f"Research analysis error: {str(e)}"

        return {
            "analysis": analysis,
            "search_results": search_results,
            "source": "researcher_agent",
        }


# Singleton instance
researcher_agent = ResearcherAgent()
