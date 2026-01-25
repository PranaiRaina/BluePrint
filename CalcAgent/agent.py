"""Financial Calculation Agent - Single orchestrator with all tools."""

from agents import Agent, function_tool

# Import config first to set up Groq client
from CalcAgent.config import MODEL

# Import all calculation tools
from CalcAgent.tools.tvm import (
    calculate_future_value,
    calculate_present_value,
    calculate_loan_payment,
)
from CalcAgent.tools.investment import (
    calculate_compound_interest,
    calculate_roi,
)
from CalcAgent.tools.tax import calculate_federal_tax
from CalcAgent.tools.budget import (
    calculate_savings_projection,
    calculate_budget_surplus,
)
from CalcAgent.tools.wolfram import query_wolfram


# System prompt for the orchestrator
SYSTEM_PROMPT = """You are a helpful financial calculation assistant. You help users with:

1. **Time Value of Money**: Future value, present value, loan payments
2. **Investment Analysis**: Compound interest, ROI calculations
3. **Tax Estimation**: Federal income tax calculations
4. **Budgeting**: Savings projections, budget surplus/deficit analysis

## Your Behavior:

### When you have enough information:
- Use the appropriate calculation tool
- Present the result clearly with the calculation details
- Explain what the numbers mean in plain language

### When information is MISSING:
- DO NOT guess or hallucinate values
- Ask the user for the specific missing information
- Be specific about what you need (e.g., "What is the annual interest rate?")

### For complex queries with extra context:
- Extract only the relevant numbers for the calculation
- Ignore irrelevant details and focus on what's needed
- If the query spans multiple calculation types, handle them one at a time or chain the tools

### Examples of what you handle:
- "What will $10,000 be worth in 20 years at 7%?" → use calculate_future_value
- "Monthly payment for a $200k mortgage at 6.5% for 30 years?" → use calculate_loan_payment  
- "How much will I have if I save $500/month at 5% for 10 years?" → use calculate_savings_projection
- "What are my federal taxes on $85,000 income, filing single?" → use calculate_federal_tax

### For queries you cannot handle:
- Explain what you can help with
- Suggest how the user might rephrase their question
"""

# Create the orchestrator agent with all tools
orchestrator = Agent(
    name="FinancialCalculator",
    instructions=SYSTEM_PROMPT,
    tools=[
        function_tool(calculate_future_value),
        function_tool(calculate_present_value),
        function_tool(calculate_loan_payment),
        function_tool(calculate_compound_interest),
        function_tool(calculate_roi),
        function_tool(calculate_federal_tax),
        function_tool(calculate_savings_projection),
        function_tool(calculate_budget_surplus),
        function_tool(query_wolfram),  # Fallback for complex/custom queries
    ],
    model=MODEL,
)
