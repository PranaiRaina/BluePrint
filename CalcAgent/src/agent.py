"""Financial Calculation Agent (Pure Specialist)."""

from datetime import datetime
from agents import Agent, function_tool

from CalcAgent.config.config import MODEL
from CalcAgent.src.schemas import CalculationResult
from CalcAgent.config.prompts import (
    FINANCIAL_AGENT_PROMPT,
    TVM_AGENT_PROMPT,
    INVESTMENT_AGENT_PROMPT,
    TAX_AGENT_PROMPT,
    BUDGET_AGENT_PROMPT,
    GENERAL_PROMPT
)
from CalcAgent.tools.wolfram import query_wolfram

# =============================================================================
# Financial Calculator Agent (Sub-Agent)
# =============================================================================
now = datetime.now()
current_date = now.strftime("%Y-%m-%d")
current_year = now.year

financial_instructions = FINANCIAL_AGENT_PROMPT.format(
    current_date=current_date,
    current_year=current_year
)

wolfram_tool = function_tool(query_wolfram)

financial_agent = Agent(
    name="FinancialCalculator",
    instructions=financial_instructions,
    tools=[wolfram_tool],
    model=MODEL,
)

general_agent = Agent(
    name="GeneralAgent",
    instructions=GENERAL_PROMPT,
    model=MODEL,
    tools=[], 
)

# =============================================================================
# Sub-Agents (Specialized)
# =============================================================================
tax_instructions = TAX_AGENT_PROMPT.format(
    current_date=current_date,
    current_year=current_year
)

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
