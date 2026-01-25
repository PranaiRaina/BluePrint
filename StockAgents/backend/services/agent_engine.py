"""
Agent Engine - Hub-and-Spoke Multi-Agent Orchestrator

This is the MAIN AGENT (Hub) that orchestrates sub-agents:
- Quant Agent: Risk analysis using Wolfram
- Researcher Agent: Market intelligence using Tavily

Architecture:
1. Detect user intent
2. Execute sub-agents in PARALLEL
3. Synthesize all intelligence into final response
"""
import asyncio
import re
from typing import Dict, Any
from .predictive_engine import predictive_engine
from .portfolio_engine import portfolio_engine
from .finnhub_client import finnhub_client
from .llm_service import llm_service

# System Prompt for the Main Agent (Portfolio Manager)
MAIN_AGENT_PROMPT = """
You are a Senior Portfolio Manager at a top-tier financial advisory firm. 

Your goal is to provide holistic, actionable, and empathetic financial advice.

### YOUR RESPONSIBILITIES:

1.  **Orchestrate:** You receive reports from your Quantitative Analyst (Quant) and Market Researcher. Combine their insights into a single, cohesive recommendation.

2.  **Verify:** Cross-reference the "Math" (Quant) with the "Sentiment" (Researcher). If there's a major discrepancy, flag it.

3.  **Synthesize:** Weave the reports together, don't just copy-paste.

4.  **SCORING RULES (CRITICAL):**
    - **START with the analystConsensusScore** from the Quant report — based on Wall Street professionals
    - Only adjust the score by ±10 points based on recent news from the Researcher
    - If 72/100 analysts say BUY, your score should be 65-80, NOT 50-60
    - NEWS should MODIFY the score, not REPLACE it

5.  **RECOMMENDATION THRESHOLDS:**
    - Under 40 → SELL
    - 40-70 → HOLD
    - Above 70 → BUY
    - Output format: "Score: X/100 — RECOMMENDATION"

6.  **Tone:** Professional, clear, and reassuring. Avoid jargon.

### CRITICAL CONSTRAINTS:
* Always include disclaimer: "I am an AI, not a certified financial advisor. Please do your own due diligence."
* If real-time price differs from expectation, point it out.
"""

class AgentEngine:
    def __init__(self):
        pass

    async def run_workflow(self, user_query: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orchestrate the OODA loop: Observe, Analyze, Decide, Act.
        Hub-and-Spoke pattern with parallel sub-agent execution.
        """
        # 1. Observe - Detect Intent
        intent = self._detect_intent(user_query)
        
        # 2. Analyze - Execute appropriate workflow
        analysis_results = {}
        sub_agent_reports = {}
        
        if intent == "market_filter":
            watchlist = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "NVDA", "META", "NFLX"]
            min_change = 0 if "gainer" in user_query.lower() or "up" in user_query.lower() else -100
            movers = await finnhub_client.filter_market_movers(watchlist, min_change_percent=min_change)
            analysis_results = {"market_movers": movers}

        elif intent == "stock_analysis":
            symbol = await self._extract_symbol(user_query) or "AAPL"
            
            # === Hub-and-Spoke: Execute Sub-Agents in Parallel ===
            quote_task = finnhub_client.get_quote(symbol)
            candles_task = finnhub_client.get_candles(symbol, resolution="D")
            
            # Import sub-agents
            from .quant_agent import quant_agent
            from .researcher_agent import researcher_agent
            
            # Parallel execution: Quote, Candles, Quant, Researcher
            results = await asyncio.gather(
                quote_task,
                candles_task,
                quant_agent(symbol),
                researcher_agent(f"Latest news and sentiment for {symbol} stock"),
                return_exceptions=True
            )
            
            quote = results[0] if not isinstance(results[0], Exception) else {}
            candles = results[1] if not isinstance(results[1], Exception) else {}
            quant_result = results[2] if not isinstance(results[2], Exception) else {"error": str(results[2])}
            research_result = results[3] if not isinstance(results[3], Exception) else {"error": str(results[3])}
            
            # Prediction using current price
            latest_close = quote.get('c', 150.0) if isinstance(quote, dict) else 150.0
            prediction = predictive_engine.predict_next({'close': latest_close})
            
            # Collect sub-agent reports for synthesis
            sub_agent_reports = {
                "quant": quant_result,
                "researcher": research_result
            }
            
            analysis_results = {
                "symbol": symbol,
                "quote": quote, 
                "candles": candles,
                "prediction": prediction,
                "risk_data": quant_result.get("risk_data", {}),
                "research": research_result.get("search_results", {})
            }
        
        elif intent == "portfolio_optimization":
            # Extract holdings for rebalancing
            holdings = await llm_service.extract_structured_data(user_query)
            
            if holdings:
                assets = list(holdings.keys())
                allocation = await portfolio_engine.optimize_portfolio(assets, {}, current_holdings=holdings)
            else:
                user_assets = self._extract_portfolio_assets(user_query)
                if not user_assets:
                    user_assets = user_context.get("portfolio", ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META"])
                allocation = await portfolio_engine.optimize_portfolio(user_assets, {})
            
            # Fetch Charts for all assets
            charts_data = {}
            target_assets = list(allocation.get("allocation", {}).keys())
            for asset in target_assets:
                charts_data[asset] = await finnhub_client.get_candles(asset, resolution="D")

            analysis_results = {
                "optimization": allocation,
                "charts": charts_data 
            }

        # 3. Decide & 4. Act - Generate Recommendation
        recommendation = await self._generate_recommendation(user_query, intent, analysis_results, sub_agent_reports)
        
        return {
            "intent": intent,
            "analysis": analysis_results,
            "recommendation": recommendation
        }

    def _detect_intent(self, query: str) -> str:
        query = query.lower()
        if "optimize" in query or "portfolio" in query or "rebalance" in query or "allocat" in query:
            return "portfolio_optimization"
        if "filter" in query or "scan" in query or "gainer" in query or "mover" in query:
            return "market_filter"
        return "stock_analysis"

    async def _extract_symbol(self, query: str) -> str:
        # 1. Try Fast Regex for obvious tickers
        words = query.split()
        for word in words:
            if word.isupper() and len(word) <= 5:
                if word not in ["WHAT", "WHEN", "HOW", "WHY", "WHO"]:
                    return word
        
        # 2. Fallback to LLM Resolution (Smart Name Search)
        return await llm_service.resolve_ticker(query)

    def _extract_portfolio_assets(self, query: str) -> list[str]:
        """Extract multiple stock symbols from query."""
        matches = re.findall(r'\b[A-Z]{2,5}\b', query)
        stop_words = {
            "WHAT", "WHEN", "HOW", "WHY", "WHO", "AND", "FOR", "THE", "ARE", 
            "IS", "NOT", "BUT", "ALL", "ANY", "CAN", "GET", "SET", "PUT", "BUY", "SELL"
        }
        assets = [m for m in matches if m not in stop_words]
        return list(set(assets))

    async def _generate_recommendation(self, query: str, intent: str, analysis: Dict, sub_agent_reports: Dict = None) -> str:
        """
        Synthesize all intelligence using the Main Agent persona.
        For stock_analysis, includes Quant and Researcher sub-agent reports.
        """
        import json
        
        # Build synthesis context
        context = {
            "intent": intent,
            "technical_data": analysis
        }
        
        # For stock analysis, use full synthesis with sub-agent reports
        if intent == "stock_analysis" and sub_agent_reports:
            quant_report = sub_agent_reports.get("quant", {}).get("analysis", "No quant data")
            research_report = sub_agent_reports.get("researcher", {}).get("analysis", "No research data")
            
            synthesis_prompt = f"""
User Query: {query}

=== QUANT AGENT REPORT ===
{quant_report}

=== RESEARCHER AGENT REPORT ===
{research_report}

=== MARKET DATA ===
{json.dumps(analysis, indent=2, default=str)[:3000]}

Based on the above reports from your team, synthesize a final recommendation for the user.
Remember to use the scoring rules from your system prompt.
"""
            try:
                from groq import AsyncGroq
                from core.config import settings
                client = AsyncGroq(api_key=settings.GROQ_API_KEY)
                
                response = await client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": MAIN_AGENT_PROMPT},
                        {"role": "user", "content": synthesis_prompt}
                    ],
                    temperature=0.5,
                    max_tokens=600
                )
                return response.choices[0].message.content
            except Exception as e:
                print(f"Synthesis error: {e}")
                return await llm_service.analyze_context(query, context)
        
        # For other intents, use standard LLM service
        return await llm_service.analyze_context(query, context)

agent_engine = AgentEngine()
