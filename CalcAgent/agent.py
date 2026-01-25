"""Financial Calculation Agent - Single Agent Architecture."""

from datetime import datetime
from agents import Agent, function_tool

from CalcAgent.config import MODEL
from CalcAgent.prompts.prompts import FINANCIAL_AGENT_PROMPT
from CalcAgent.tools.wolfram import query_wolfram

# Create the function tool for Wolfram
# In single-agent mode, we expose this directly to the main agent
wolfram_tool = function_tool(query_wolfram)

# Get current date context
now = datetime.now()
current_date = now.strftime("%Y-%m-%d")
current_year = now.year

# Format system prompt with dynamic date
agent_instructions = FINANCIAL_AGENT_PROMPT.format(
    current_date=current_date,
    current_year=current_year
)

# Create the Single Financial Agent
# We use the variable name 'orchestrator' so main.py doesn't need changes (it imports orchestrator)
orchestrator = Agent(
    name="FinancialHelper",
    instructions=agent_instructions,
    tools=[wolfram_tool],  # Direct access to Wolfram, no sub-agents
    model=MODEL,
)
