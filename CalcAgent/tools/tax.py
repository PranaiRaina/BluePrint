"""Tax calculation tools."""

from CalcAgent.tools.wolfram import query_wolfram


async def calculate_federal_tax(income: float, filing_status: str = "single") -> str:
    """
    Estimate federal income tax liability.
    
    Args:
        income: Annual taxable income
        filing_status: Filing status - "single", "married", "married_separate", or "head_of_household"
    
    Returns:
        Tax calculation result from Wolfram Alpha
    """
    query = f"US federal income tax on ${income:,.2f} filing {filing_status}"
    return await query_wolfram(query)
