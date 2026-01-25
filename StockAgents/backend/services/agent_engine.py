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

Your goal is to provide holistic, actionable, and empathetic financial advice to your client.

### YOUR RESPONSIBILITIES:

1.  **Orchestrate:** You have a team of sub-agents (a Quantitative Analyst and a Market Researcher). You will receive their reports. Your job is to combine their insights into a single, cohesive recommendation.

2.  **Verify:** Cross-reference the "Math" (Quant) with the "Sentiment" (Researcher). If there's a major discrepancy, flag it.

3.  **Synthesize:** Weave the reports together, don't just copy-paste.

4.  **SCORING RULES (CRITICAL):**
    - **START with the analystConsensusScore** from the Quant report — this is based on 30-50+ Wall Street professionals
    - Only adjust the score by ±10 points based on recent news from the Researcher
    - If 72/100 analysts say BUY, your score should be 65-80, NOT 50-60
    - NEWS should MODIFY the score, not REPLACE it
    - Example: Analyst says 72/100 (BUY), Researcher says "minor concerns" → Your score: 68/100 (still BUY)

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

    async def _analyze_single_stock(self, symbol: str) -> Dict[str, Any]:
        """
        Run the full Hub-and-Spoke workflow for a SINGLE stock.
        Returns: { symbol, quote, candles, quant, researcher, prediction }
        """
        # Import sub-agents
        from .quant_agent import quant_agent
        from .researcher_agent import researcher_agent
        
        # Parallel execution: Quote, Candles, Quant, Researcher
        results = await asyncio.gather(
            finnhub_client.get_quote(symbol),
            finnhub_client.get_candles(symbol, resolution="D"),
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
        
        return {
            "symbol": symbol,
            "quote": quote,
            "candles": candles,
            "quant": quant_result,
            "researcher": research_result,
            "prediction": prediction
        }

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
            # Extract ONE symbol for single-stock analysis
            symbol = await self._extract_symbol(user_query) or "AAPL"
            
            # Execute single stock workflow
            stock_data = await self._analyze_single_stock(symbol)
            
            analysis_results = {
                "symbol": symbol,
                "quote": stock_data["quote"], 
                "candles": stock_data["candles"],
                "prediction": stock_data["prediction"],
                "risk_data": stock_data["quant"].get("risk_data", {}),
                "research": stock_data["researcher"].get("search_results", {})
            }
            sub_agent_reports = {
                "quant": stock_data["quant"],
                "researcher": stock_data["researcher"]
            }
        
        elif intent == "portfolio_optimization" or intent == "stock_comparison":
            # Extract ALL involved assets
            holdings = await llm_service.extract_structured_data(user_query)
            user_assets = list(holdings.keys()) if holdings else await llm_service.extract_tickers_list(user_query)
            
            if not user_assets and intent == "portfolio_optimization":
                user_assets = user_context.get("portfolio", ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META"])
            
            # Limit to 3 assets for performance if it's a broad optimization, but allow more for specific comparison
            target_assets = user_assets[:4] 

            # === Parallel Deep Analysis for EACH Asset ===
            # Run sub-agents for all targets in parallel
            analysis_tasks = [self._analyze_single_stock(asset) for asset in target_assets]
            multi_stock_results = await asyncio.gather(*analysis_tasks)
            
            # Structure results for synthesis
            sub_agent_reports = {
                "multi_stock": True,
                "reports": {res["symbol"]: res for res in multi_stock_results}
            }
            
            # Also run Portfolio Optimization (allocation)
            allocation = await portfolio_engine.optimize_portfolio(target_assets, {}, current_holdings=holdings or {})
            
            # Fetch Charts for all assets
            charts_data = {res["symbol"]: res["candles"] for res in multi_stock_results}

            analysis_results = {
                "optimization": allocation,
                "charts": charts_data,
                "deep_analysis": sub_agent_reports["reports"] # Include deep data in analysis
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
        if "compare" in query or "vs" in query or "better" in query:
             return "stock_comparison"
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
                if word not in ["WHAT", "WHEN", "HOW", "WHY", "WHO", "I", "A", "OR", "IF", "IS", "IT", "TO", "DO", "BUY", "SELL"]:
                    return word
        
        # 2. Fallback to LLM Resolution (Smart Name Search)
        return await llm_service.resolve_ticker(query)

    def _extract_portfolio_assets(self, query: str) -> list[str]:
        """Extract multiple stock symbols from query."""
        matches = re.findall(r'\b[A-Z]{2,5}\b', query)
        stop_words = {
            "WHAT", "WHEN", "HOW", "WHY", "WHO", "AND", "FOR", "THE", "ARE", 
            "IS", "NOT", "BUT", "ALL", "ANY", "CAN", "GET", "SET", "PUT", "BUY", "SELL",
            "VS", "OR", "BETWEEN", "COMPARE", "GIVE", "SHOW", "TELL", "ME", "ABOUT", "OPTIMIZE"
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
        
        synthesis_prompt = ""

        # Case 1: Single Stock Analysis
        if intent == "stock_analysis" and sub_agent_reports:
            quant_report = sub_agent_reports.get("quant", {}).get("analysis", "No quant data")
            research_report = sub_agent_reports.get("researcher", {}).get("analysis", "No research data")
            
            # Extract rich data for single stock
            # Notes: 'quant' result contains 'risk_data' with full analyst metrics
            risk_data = sub_agent_reports.get("quant", {}).get("risk_data", {})
            analyst_score = risk_data.get('analystConsensusScore', 'N/A')
            buy_count = risk_data.get('buyCount', 'N/A')
            sell_count = risk_data.get('sellCount', 'N/A')
            total_analysts = risk_data.get('totalAnalysts', 'N/A')
            pe_ratio = risk_data.get('peRatio', 'N/A')
            
            synthesis_prompt = f"""
User Query: {query}

=== KEY FINANCIAL METRICS ===
PRICE: ${analysis.get('quote', {}).get('c', 'N/A')}
ANALYST CONSENSUS SCORE: {analyst_score}/100
WALL STREET OPINION: {buy_count} Buy vs {sell_count} Sell (from {total_analysts} analysts)
P/E RATIO: {pe_ratio}
BETA: {risk_data.get('beta', 'N/A')}

=== QUANT AGENT REPORT ===
{quant_report}

=== RESEARCHER AGENT REPORT ===
{research_report}

=== INSTRUCTIONS ===
You are a Financial Analyst.
**FORMATTING RULE**: OUTPUT AS PLAIN TEXT LISTS.
**ABSOLUTELY NO MARKDOWN TABLES**.
**ABSOLUTELY NO PIPES (|) or TABLE ROWS**.

**Required Format:**

### 1. Comparison Summary
(Use a bulleted list to compare metrics)
*   **[Ticker]**: Price: $X // Score: Y // P/E: Z // Recomm: Buy/Sell
*Example:*
*   **AAPL**: Price: $150 // Score: 85 // P/E: 25x // Buy
*   **MSFT**: Price: $250 // Score: 80 // P/E: 30x // Hold

### 2. Deep Dive
(For each ticker, detailed bullet points)
*   **Price**: ...
*   **Consensus**: ...
*   **Metrics**: ...
*   **Analysis**: ...

### 3. Verdict
*   **Winner**: [Ticker]
*   **Score**: X/100
*   **Why**: [One sentence]
"""
        
        # Case 2: Multi-Stock Comparison / Optimization
        elif (intent == "stock_comparison" or intent == "portfolio_optimization") and sub_agent_reports and "multi_stock" in sub_agent_reports:
             reports = sub_agent_reports.get("reports", {})
             
             reports_text = ""
             for symbol, data in reports.items():
                 # Extract analyst data directly to ensure it's available
                 quant_data = data.get('quant', {}).get('risk_data', {})
                 analyst_score = quant_data.get('analystConsensusScore', 'N/A')
                 analyst_rec = quant_data.get('analystRecommendation', 'N/A')
                 total_analysts = quant_data.get('totalAnalysts', 'N/A')
                 buy_count = quant_data.get('buyCount', 0)
                 sell_count = quant_data.get('sellCount', 0)
                 
                 reports_text += f"""
--- ANALYSIS FOR {symbol} ---
PRICE: ${data['quote'].get('c', 'N/A')}
ANALYST CONSENSUS: {analyst_score}/100 ({analyst_rec})
WALL STREET OPINION: {buy_count} Buy vs {sell_count} Sell (from {total_analysts} analysts)
KEY METRICS: Beta: {quant_data.get('beta', 'N/A')}, P/E: {quant_data.get('peRatio', 'N/A')}

QUANT ANALYSIS: 
{data['quant'].get('analysis', 'N/A')}

RESEARCH SUMMARY:
{data['researcher'].get('analysis', 'N/A')}
-----------------------------
"""
             synthesis_prompt = f"""
User Query: {query}

You are a Senior Portfolio Manager. Compare these assets using the data below.
CRITICAL: You MUST use specific numbers and evidence.

{reports_text}

=== OPTIMIZATION DATA ===
{json.dumps(analysis.get('optimization', {}), indent=2, default=str)}

INSTRUCTIONS:
1. **Data Comparison Table**: Create a Markdown table comparing Price, Analyst Score, P/E Ratio, and Wall Street Signal (Buy/Sell counts) for each stock.
2. **Deep Dive**: For each stock, provide specific evidence (e.g., "Apple has 35 Buy ratings...", "Meta's P/E is...").
3. **Wall Street Consensus**: Explicitly state what Finnhub data says about analyst opinions.
4. **Recommendation**: Conclude with a clear, data-backed verdict.
"""

        # Execute Synthesis if we have a prompt
        if synthesis_prompt:
            try:
                from groq import AsyncGroq
                from StockAgents.backend.core.config import settings
                client = AsyncGroq(api_key=settings.GROQ_API_KEY)
                
                response = await client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=[
                        {"role": "system", "content": MAIN_AGENT_PROMPT},
                        {"role": "user", "content": synthesis_prompt}
                    ],
                    temperature=0.5,
                    max_tokens=1000
                )
                response_text = response.choices[0].message.content
                return response_text + "\n\n_Data Sources: Finnhub (Real-Time Price & Analyst Ratings), Yahoo Finance (Historical Volatility), Tavily (Market News)._"
            except Exception as e:
                print(f"Synthesis error: {e}")
                return await llm_service.analyze_context(query, context)
        
        # For other intents, use standard LLM service
        return await llm_service.analyze_context(query, context)

agent_engine = AgentEngine()
