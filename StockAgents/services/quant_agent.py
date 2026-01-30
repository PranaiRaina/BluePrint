"""
Quant Agent - Risk Analysis Sub-Agent

Uses Wolfram Cloud for mathematical computations and Finnhub for analyst ratings.
Persona: Dry, numerical, focused on data.
"""

import json
import asyncio
from typing import Dict, Any
from concurrent.futures import ThreadPoolExecutor
from StockAgents.core.prompts import QUANT_SYSTEM_PROMPT
from .base_agent import BaseAgent
from .llm_service import llm_service

# Thread pool for blocking Wolfram calls
executor = ThreadPoolExecutor(max_workers=3)


class QuantAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Quant", client=llm_service.client)
        self.model = "gemini-2.0-flash"

    async def run(self, ticker: str) -> Dict[str, Any]:
        """
        Execute quantitative analysis.
        Logic:
        1. Always get Price History & Company Metrics (Fast).
        2. Always get Analyst Ratings (Fast).
        3. Only run Wolfram Risk model (Slow) if necessary?
           - For now, we keep it as is, but structured as a class method.
        """
        from StockAgents.tools.wolfram_tool import wolfram_risk_analysis
        from StockAgents.tools.yfinance_tool import get_historical_prices
        from StockAgents.services.finnhub_client import finnhub_client

        ticker = ticker.upper().strip()
        loop = asyncio.get_running_loop()

        # Step 1: Parallel Fetch (Metrics, Analysts, History)
        # We can run these concurrently
        task_history = loop.run_in_executor(executor, get_historical_prices, ticker)
        task_metrics = finnhub_client.get_company_metrics(ticker)
        task_ratings = finnhub_client.get_analyst_ratings(ticker)

        results = await asyncio.gather(task_history, task_metrics, task_ratings)
        history, metrics, analyst_ratings = results

        prices = history.get("prices", []) if "error" not in history else []

        # Step 2: Risk Analysis (Wolfram) - still blocking/slow
        risk_data = await loop.run_in_executor(
            executor, wolfram_risk_analysis, ticker, prices, metrics, analyst_ratings
        )

        # Step 3: Synthesis
        messages = [
            {"role": "system", "content": QUANT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Analyze this risk data for {ticker}:\n\n{json.dumps(risk_data, indent=2)}\n\nProvide a quantitative risk assessment.",
            },
        ]

        try:
            response = await self.client.chat.completions.create(
                model=self.model, messages=messages, temperature=0.3, max_tokens=400
            )
            analysis = response.choices[0].message.content
        except Exception as e:
            analysis = f"Quant analysis error: {str(e)}"

        return {"analysis": analysis, "risk_data": risk_data, "source": "quant_agent"}


# Singleton instance
quant_agent = QuantAgent()
