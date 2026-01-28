"""SubAgents for financial calculations - each has Wolfram as their tool."""

from datetime import datetime
from agents import Agent, function_tool
from CalcAgent.config import MODEL
from CalcAgent.tools.wolfram import query_wolfram
from CalcAgent.schemas import CalculationResult
from CalcAgent.config.prompts import (
    TVM_AGENT_PROMPT,
    INVESTMENT_AGENT_PROMPT,
    TAX_AGENT_PROMPT,
    BUDGET_AGENT_PROMPT,
)

wolfram_tool = function_tool(query_wolfram)

now = datetime.now()
current_date = now.strftime("%Y-%m-%d")
current_year = now.year

tax_instructions = TAX_AGENT_PROMPT.format(
    current_date=current_date,
    current_year=current_year
)


# =============================================================================
# SubAgents with Structured Outputs
# =============================================================================
tvm_agent = Agent(
    name="TVMAgent",
    instructions=TVM_AGENT_PROMPT,
    tools=[wolfram_tool],
    model=MODEL,
    output_type=CalculationResult,
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
    instructions=tax_instructions,
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
