"""Manager Agent (Router) Logic."""

from agents import Agent, function_tool

from CalcAgent.config.config import MODEL
from CalcAgent.config.prompts import MANAGER_PROMPT
from CalcAgent.agent import financial_agent
from ManagerAgent.tools import perform_rag_search, ask_stock_analyst

# Tool wrapper for RAG
rag_tool = function_tool(perform_rag_search)

# Tool wrapper for Stock Analysis
stock_tool = function_tool(ask_stock_analyst)

# The Manager Agent
# Directs traffic between Financial Calculator (Handoff) and RAG (Tool)
from agents import Runner

async def ask_financial_calculator(query: str) -> str:
    """
    Delegate a complex financial question to the Financial Expert Agent.
    Use this for any math, mortgage, tax, or investment calculation.
    """
    # Run the sub-agent and return its final answer
    result = await Runner.run(financial_agent, query)
    return result.final_output

# Tool wrapper for Calculator
calculator_tool = function_tool(ask_financial_calculator)

# The Manager Agent
# Directs traffic between Financial Calculator (Tool), RAG (Tool), and Stock Analysis (Tool)
manager_agent = Agent(
    name="ManagerAgent",
    instructions=MANAGER_PROMPT,
    model=MODEL,
    tools=[
        rag_tool, 
        calculator_tool,
        stock_tool
    ]
)
