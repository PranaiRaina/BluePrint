"""SubAgents for financial calculations - each has Wolfram as their tool."""

from agents import Agent, function_tool
from CalcAgent.config import MODEL
from CalcAgent.tools.wolfram import query_wolfram
from CalcAgent.schemas import CalculationResult
from CalcAgent.prompts.prompts import (
    TVM_AGENT_PROMPT,
    INVESTMENT_AGENT_PROMPT,
    TAX_AGENT_PROMPT,
    BUDGET_AGENT_PROMPT,
)

# Shared Wolfram tool for all subagents
wolfram_tool = function_tool(query_wolfram)


# =============================================================================
# SubAgents with Structured Outputs
# =============================================================================
tvm_agent = Agent(
    name="TVMAgent",
    instructions=TVM_AGENT_PROMPT,
    tools=[wolfram_tool],
    model=MODEL,
    output_type=CalculationResult,  # Enforces structured response
)

investment_agent = Agent(
    name="InvestmentAgent",
    instructions=INVESTMENT_AGENT_PROMPT,
    tools=[wolfram_tool],
    model=MODEL,
    output_type=CalculationResult,
)

tax_agent = Agent(
    name="TaxAgent",
    instructions=TAX_AGENT_PROMPT,
    tools=[wolfram_tool],
    model=MODEL,
    output_type=CalculationResult,
)

budget_agent = Agent(
    name="BudgetAgent",
    instructions=BUDGET_AGENT_PROMPT,
    tools=[wolfram_tool],
    model=MODEL,
    output_type=CalculationResult,
)
