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
from typing import Dict, Any, List, Optional, Union
from pydantic import BaseModel, Field
import json
from .finnhub_client import finnhub_client
from .llm_service import llm_service
from StockAgents.backend.core.prompts import MAIN_AGENT_PROMPT, PLANNER_SYSTEM_PROMPT

# System Prompt for the Main Agent (Portfolio Manager)



# --- Planner Models ---

class PlannerStep(BaseModel):
    tool: str = Field(..., description="The tool to call. Allowed: market_scan, get_stock_data, quant_analysis, news_research")
    args: Dict[str, Any] = Field({}, description="Arguments for the tool call")
    description: str = Field(..., description="Brief description of what this step does")

class ExecutionPlan(BaseModel):
    reasoning: str = Field(..., description="Reasoning behind the plan")
    steps: List[PlannerStep] = Field(..., description="Ordered list of steps to execute")

class LLMPlanner:
    def __init__(self, llm_client):
        self.client = llm_client
        # Define available tools for the planner
        self.tools_schema = """
        AVAILABLE TOOLS:
        1. market_scan(min_change_percent: float, sector: str)
           - Use for: "top gainers", "market movers", "tech stocks up today".
           
        2. get_stock_data(ticker: str)
           - Use for: "price of Apple", "show me a chart of MSFT", "how is NVDA doing".
           - Returns: Real-time price, candles (chart data).
           
        3. quant_analysis(ticker: str)
           - Use for: "risk analysis", "beta", "should I buy AAPL (technical)", "deep dive".
           - Returns: Analyst ratings, volatility, risk score.
           
        4. news_research(query: str)
           - Use for: "why is TSLA down", "latest news on Meta", "market sentiment".
           - Returns: News summaries, sentiment analysis.
        """
        
    async def create_plan(self, user_query: str) -> ExecutionPlan:
        system_prompt = PLANNER_SYSTEM_PROMPT.format(tools_schema=self.tools_schema)
        
        try:
            response = await self.client.chat.completions.create(
                model="gemini-2.0-flash", # Use same model as other services
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query}
                ],
                response_format={"type": "json_object"},
                temperature=0.0
            )
            content = response.choices[0].message.content
            return ExecutionPlan.model_validate_json(content)
        except Exception as e:
            print(f"Planning Error: {e}")
            # Fallback Plan (assume simple stock check)
            return ExecutionPlan(
                reasoning="Fallback due to error",
                steps=[
                    PlannerStep(tool="news_research", args={"query": user_query}, description="Fallback search")
                ]
            )

class AgentEngine:
    def __init__(self):
        self.planner = LLMPlanner(llm_service.client)

    async def run_workflow(self, user_query: str, user_context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Orchestrate the OODA loop: Observe, Analyze, Decide, Act.
        Dynamic execution based on LLM Plan.
        """
        # 1. Plan
        plan = await self.planner.create_plan(user_query)
        print(f"Generated Plan: {plan.dict()}")
        
        # 2. Execute
        execution_results = {}
        charts_data = {}
        
        # Helper to run tools safely
        async def execute_step(step: PlannerStep):
            try:
                if step.tool == "market_scan":
                    return await finnhub_client.filter_market_movers(
                        step.args.get("sector", "Technology"),
                        min_change_percent=step.args.get("min_change_percent", 0)
                    )
                elif step.tool == "get_stock_data":
                    ticker = step.args.get("ticker", "AAPL").upper()
                    quote = await finnhub_client.get_quote(ticker)
                    candles = await finnhub_client.get_candles(ticker, resolution="D")
                    # Store chart data separately for frontend
                    if candles.get("s") == "ok":
                        charts_data[ticker] = candles.get("c", []) 
                    return {"quote": quote, "candles": candles}
                elif step.tool == "quant_analysis":
                    from .quant_agent import quant_agent
                    return await quant_agent(step.args.get("ticker", "AAPL"))
                elif step.tool == "news_research":
                    from .researcher_agent import researcher_agent
                    return await researcher_agent(step.args.get("query", user_query))
                else:
                    return {"error": f"Unknown tool: {step.tool}"}
            except Exception as e:
                return {"error": f"Step failed: {str(e)}"}

        # Execute steps sequentially
        for i, step in enumerate(plan.steps):
            result = await execute_step(step)
            execution_results[f"step_{i}_{step.tool}"] = result
        
        # 3. Synthesize
        recommendation = await self._generate_recommendation(user_query, plan, execution_results)
        
        return {
            "intent": "dynamic_plan",
            "plan": plan.dict(),
            "analysis": {
                "charts": charts_data, # For frontend visualization
                "results": execution_results
            },
            "recommendation": recommendation
        }

    async def _generate_recommendation(self, query: str, plan: ExecutionPlan, results: Dict) -> str:
        """
        Synthesize results into a final answer.
        """
        from datetime import datetime
        
        context_str = json.dumps(results, indent=2, default=str)
        plan_str = json.dumps(plan.dict(), indent=2)
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Use simple synthesis based on Main Agent Persona
        system_prompt = MAIN_AGENT_PROMPT + "\n\nACT AS A SYNTHESIZER. Combine the tool outputs into a coherent response matching the user's intent."
        
        user_msg = f"""
        Current Date: {current_date}
        User Query: {query}
        
        Execution Plan:
        {plan_str}
        
        Tool Outputs:
        {context_str}
        
        Instructions:
        1. Answer the user's question directly.
        2. Use the data from Tool Outputs to back up your claims.
        3. If multiple stocks were analyzed, provide a comparison.
        4. If a 'quant_analysis' was done, include the Analyst Score and Risk warning.
        5. EXPLICITLY mention the 'Current Date' provided above when stating prices or status.
        6. Do not mention "Knowledge Cutoff".
        
        7.  **SCORING RULES (CRITICAL):**
            - **START with the analystConsensusScore** from the Quant report — this is based on 30-50+ Wall Street professionals.
            - Only adjust the score by ±10 points based on recent news from the Researcher.
            - **TRANSPARENCY RULE**: If you adjust the score, **YOU MUST STATE WHY**.
            - *Bad Example*: "Score: 68/100" (when raw was 72).
            - *Good Example*: "Score adjusted from 72 (Consensus) to 68 due to recent negative regulatory news."

        8.  **RECOMMENDATION THRESHOLDS:**
            - Under 40 → SELL
            - 40-70 → HOLD
            - Above 70 → BUY
            - Output format: "Score: X/100 — RECOMMENDATION"

        **FORMATTING RULES (CRITICAL):**
        - **USE MARKDOWN TABLES** for any comparison data (Price, Score, P/E, etc.).
        - **Structure your response** as: 
            1. **Executive Summary** (Table)
            2. **Deep Dive** (Bullet points)
            3. **Verdict** (Conclusion)
        - **DO NOT** include a "Disclaimer" or "I am an AI" statement in your text body. This is handled by the user interface globally.
        """
        
        try:
            response = await llm_service.client.chat.completions.create(
                model="gemini-2.0-flash",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg}
                ],
                temperature=0.5
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating recommendation: {e}. Raw Data: {str(results)}"

agent_engine = AgentEngine()