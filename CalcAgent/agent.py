"""Financial Calculation Agent (Pure Specialist)."""

from datetime import datetime
from agents import Agent, function_tool

from CalcAgent.config.config import MODEL
from CalcAgent.config.prompts import FINANCIAL_AGENT_PROMPT
from CalcAgent.tools.wolfram import query_wolfram

# =============================================================================
# Financial Calculator Agent (Sub-Agent)
# =============================================================================
# Get current date context for Financial Agent
now = datetime.now()
current_date = now.strftime("%Y-%m-%d")
current_year = now.year

# Format system prompt
financial_instructions = FINANCIAL_AGENT_PROMPT.format(
    current_date=current_date,
    current_year=current_year
)

# Tool wrapper
wolfram_tool = function_tool(query_wolfram)

financial_agent = Agent(
    name="FinancialCalculator",
    instructions=financial_instructions,
    tools=[wolfram_tool],
    model=MODEL,
)
