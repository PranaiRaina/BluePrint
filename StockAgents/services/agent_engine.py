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
from typing import Dict, Any, List
from pydantic import BaseModel, Field
import json
from .finnhub_client import finnhub_client
from .llm_service import llm_service
from StockAgents.core.prompts import MAIN_AGENT_PROMPT, PLANNER_SYSTEM_PROMPT

# System Prompt for the Main Agent (Portfolio Manager)


# --- Planner Models ---


class PlannerStep(BaseModel):
    tool: str = Field(
        ...,
        description="The tool to call. Allowed: market_scan, get_stock_data, quant_analysis, news_research",
    )
    args: Dict[str, Any] = Field({}, description="Arguments for the tool call")
    description: str = Field(
        ..., description="Brief description of what this step does"
    )


class ExecutionPlan(BaseModel):
    reasoning: str = Field(..., description="Reasoning behind the plan")
    steps: List[PlannerStep] = Field(
        ..., description="Ordered list of steps to execute"
    )


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

    async def create_plan(
        self, user_query: str, user_context: Dict[str, Any] = {}
    ) -> ExecutionPlan:
        # Format prompt with tools AND user context
        context_str = json.dumps(user_context, indent=2, default=str)
        system_prompt = PLANNER_SYSTEM_PROMPT.format(
            tools_schema=self.tools_schema, user_context=context_str
        )

        try:
            response = await self.client.chat.completions.create(
                model="gemini-2.5-flash",  # Use same model as other services
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_query},
                ],
                response_format={"type": "json_object"},
                temperature=0.0,
            )
            content = response.choices[0].message.content
            return ExecutionPlan.model_validate_json(content)
        except Exception as e:
            print(f"Planning Error: {e}")
            # Surface error to user instead of silent fallback
            raise ValueError(f"Unable to create execution plan: {str(e)}")


class AgentEngine:
    def __init__(self):
        self.planner = LLMPlanner(llm_service.client)

    async def run_workflow_stream(self, user_query: str, user_context: Dict[str, Any]):
        """
        Streaming version of run_workflow.
        Yields:
            Reading: {"type": "status", "content": "..."}
            Tokens:  {"type": "token", "content": "..."}
        """
        # 1. Plan
        yield {"type": "status", "content": "Planning analysis..."}
        plan = await self.planner.create_plan(user_query, user_context)
        print(f"Generated Plan: {plan.dict()}")

        # 2. Execute
        execution_results = {}
        charts_data = {}

        # Helper to run tools safely (Same as sync)
        async def execute_step(step: PlannerStep):
            try:
                if step.tool == "market_scan":
                    return await finnhub_client.filter_market_movers(
                        step.args.get("sector", "Technology"),
                        min_change_percent=step.args.get("min_change_percent", 0),
                    )
                elif step.tool == "get_stock_data":
                    ticker = step.args.get("ticker")
                    if not ticker:
                        return {"error": "Missing ticker argument for get_stock_data"}
                    ticker = ticker.upper()
                    quote = await finnhub_client.get_quote(ticker)
                    candles = await finnhub_client.get_candles(ticker, resolution="D")
                    # Store chart data separately for frontend
                    if candles.get("s") == "ok":
                        charts_data[ticker] = candles.get("c", [])
                    return {"quote": quote, "candles": candles}
                elif step.tool == "quant_analysis":
                    from .quant_agent import quant_agent

                    ticker = step.args.get("ticker")
                    if not ticker:
                        return {"error": "Missing ticker argument for quant_analysis"}
                    return await quant_agent.run(ticker)
                elif step.tool == "news_research":
                    from .researcher_agent import researcher_agent

                    return await researcher_agent.run(
                        step.args.get("query", user_query)
                    )
                else:
                    return {"error": f"Unknown tool: {step.tool}"}
            except Exception as e:
                return {"error": f"Step failed: {str(e)}"}

        # Helper for friendly status
        tool_display_names = {
            "market_scan": "Scanning Market...",
            "get_stock_data": "Fetching Prices...",
            "quant_analysis": "Analyzing Risk...",
            "news_research": "Reading News...",
        }

        # Execute steps sequentially
        for i, step in enumerate(plan.steps):
            display_status = tool_display_names.get(step.tool, "Working...")
            yield {"type": "status", "content": display_status}
            result = await execute_step(step)
            execution_results[f"step_{i}_{step.tool}"] = result

        # 3. Synthesize (Streaming)
        yield {"type": "status", "content": "Synthesizing recommendation..."}
        async for chunk in self._generate_recommendation_stream(
            user_query, plan, execution_results, user_context
        ):
            yield chunk

    async def run_workflow(
        self, user_query: str, user_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Orchestrate the OODA loop: Observe, Analyze, Decide, Act.
        Dynamic execution based on LLM Plan.
        """
        # ... (Original implementation kept for backward compatibility if needed, logic duplicated for simplicity in prompt)
        # Using run_workflow_stream internally and collecting result would be DRY-er but more complex change.
        # For minimal diff, I'll keep the original run_workflow as is.
        # 1. Plan
        plan = await self.planner.create_plan(user_query, user_context)
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
                        min_change_percent=step.args.get("min_change_percent", 0),
                    )
                elif step.tool == "get_stock_data":
                    ticker = step.args.get("ticker")
                    if not ticker:
                        return {"error": "Missing ticker argument for get_stock_data"}
                    ticker = ticker.upper()
                    quote = await finnhub_client.get_quote(ticker)
                    candles = await finnhub_client.get_candles(ticker, resolution="D")
                    if candles.get("s") == "ok":
                        charts_data[ticker] = candles.get("c", [])
                    return {"quote": quote, "candles": candles}
                elif step.tool == "quant_analysis":
                    from .quant_agent import quant_agent

                    ticker = step.args.get("ticker")
                    if not ticker:
                        return {"error": "Missing ticker argument for quant_analysis"}
                    return await quant_agent.run(ticker)
                elif step.tool == "news_research":
                    from .researcher_agent import researcher_agent

                    return await researcher_agent.run(
                        step.args.get("query", user_query)
                    )
                else:
                    return {"error": f"Unknown tool: {step.tool}"}
            except Exception as e:
                return {"error": f"Step failed: {str(e)}"}

        # Execute steps sequentially
        for i, step in enumerate(plan.steps):
            result = await execute_step(step)
            execution_results[f"step_{i}_{step.tool}"] = result

        # 3. Synthesize
        recommendation = await self._generate_recommendation(
            user_query, plan, execution_results, user_context
        )

        return {
            "intent": "dynamic_plan",
            "plan": plan.dict(),
            "analysis": {
                "charts": charts_data,  # For frontend visualization
                "results": execution_results,
            },
            "recommendation": recommendation,
        }

    async def _generate_recommendation(
        self,
        query: str,
        plan: ExecutionPlan,
        results: Dict,
        user_context: Dict[str, Any] = {},
    ) -> str:
        """
        Synthesize results into a final answer.
        """
        from datetime import datetime

        context_str = json.dumps(results, indent=2, default=str)
        user_context_str = json.dumps(user_context, indent=2, default=str)
        plan_str = json.dumps(plan.dict(), indent=2)
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Use simple synthesis based on Main Agent Persona
        system_prompt = (
            MAIN_AGENT_PROMPT
            + "\n\nACT AS A SYNTHESIZER. Combine the tool outputs into a coherent response matching the user's intent."
        )

        user_msg = f"""
        Current Date: {current_date}
        User Query: {query}
        
        User Portfolio Context:
        {user_context_str}
        
        Execution Plan:
        {plan_str}
        
        Tool Outputs:
        {context_str}
        
        Instructions:
        1. **PRIORITY**: If the user asks about their holdings (e.g., "how many", "do I own"), YOU MUST answer that first using the 'User Portfolio Context'.
        2. Answer the user's question directly.
        3. Use the data from Tool Outputs to back up your claims.
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
            - Under 40 → STRONG SELL
            - 40-50 → WEAK SELL
            - 50-65 → HOLD
            - 65-72 → MODERATE BUY
            - Above 72 → STRONG BUY

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
                model="gemini-2.5-flash",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.5,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating recommendation: {e}. Raw Data: {str(results)}"

    async def _generate_recommendation_stream(
        self,
        query: str,
        plan: ExecutionPlan,
        results: Dict,
        user_context: Dict[str, Any] = {},
    ):
        """
        Streamed synthesis.
        """
        from datetime import datetime

        context_str = json.dumps(results, indent=2, default=str)
        user_context_str = json.dumps(user_context, indent=2, default=str)
        plan_str = json.dumps(plan.dict(), indent=2)
        current_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Use simple synthesis based on Main Agent Persona (Same prompt as sync)
        system_prompt = (
            MAIN_AGENT_PROMPT
            + "\n\nACT AS A SYNTHESIZER. Combine the tool outputs into a coherent response matching the user's intent."
        )

        user_msg = f"""
        Current Date: {current_date}
        User Query: {query}
        
        User Portfolio Context:
        {user_context_str}
        
        Execution Plan:
        {plan_str}
        
        Tool Outputs:
        {context_str}
        
        Instructions:
        1. **PRIORITY**: If the user asks about their holdings (e.g., "how many", "do I own"), YOU MUST answer that first using the 'User Portfolio Context'.
        2. Answer the user's question directly.
        3. Use the data from Tool Outputs to back up your claims.
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
            - Under 40 → STRONG SELL
            - 40-50 → WEAK SELL
            - 50-65 → HOLD
            - 65-72 → MODERATE BUY
            - Above 72 → STRONG BUY

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
            stream = await llm_service.client.chat.completions.create(
                model="gemini-2.5-flash",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.5,
                stream=True,
            )

            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield {"type": "token", "content": chunk.choices[0].delta.content}
                    await asyncio.sleep(0)  # Force buffer flush

        except Exception as e:
            yield {"type": "token", "content": f"Error generating recommendation: {e}."}


agent_engine = AgentEngine()
