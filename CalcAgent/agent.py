"""Financial Calculation Agent - Orchestrator with SubAgents as tools."""

from agents import Agent

from CalcAgent.config import MODEL
from CalcAgent.prompts.prompts import ORCHESTRATOR_PROMPT
from CalcAgent.subagents import (
    tvm_agent,
    investment_agent,
    tax_agent,
    budget_agent,
)

# Create the orchestrator agent with subagents as tools
orchestrator = Agent(
    name="FinancialCalculator",
    instructions=ORCHESTRATOR_PROMPT,
    tools=[
        tvm_agent.as_tool(
            tool_name="tvm_agent",
            tool_description="Time Value of Money specialist - handles future value, present value, and loan payment calculations. Returns structured result with answer, explanation, and formula.",
        ),
        investment_agent.as_tool(
            tool_name="investment_agent", 
            tool_description="Investment specialist - handles compound interest, ROI, and CAGR calculations. Returns structured result with answer, explanation, and formula.",
        ),
        tax_agent.as_tool(
            tool_name="tax_agent",
            tool_description="Tax specialist - handles federal income tax and tax bracket calculations. Returns structured result with answer, explanation, and formula.",
        ),
        budget_agent.as_tool(
            tool_name="budget_agent",
            tool_description="Budget specialist - handles savings projections and budget analysis. Returns structured result with answer, explanation, and formula.",
        ),
    ],
    model=MODEL,
)
