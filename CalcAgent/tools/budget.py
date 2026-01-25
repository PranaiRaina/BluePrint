"""Budget and savings calculation tools."""

from CalcAgent.tools.wolfram import query_wolfram


async def calculate_savings_projection(monthly_contribution: float, annual_rate: float, years: int) -> str:
    """
    Calculate future savings with regular monthly contributions.
    
    Args:
        monthly_contribution: Amount saved each month
        annual_rate: Expected annual return rate as a percentage (e.g., 5 for 5%)
        years: Number of years to save
    
    Returns:
        Savings projection from Wolfram Alpha
    """
    query = f"future value of ${monthly_contribution:,.2f} monthly deposits at {annual_rate}% annual interest for {years} years"
    return await query_wolfram(query)


async def calculate_budget_surplus(monthly_income: float, monthly_expenses: float) -> str:
    """
    Calculate monthly budget surplus or deficit.
    
    Args:
        monthly_income: Total monthly income after taxes
        monthly_expenses: Total monthly expenses
    
    Returns:
        Budget analysis with surplus/deficit
    """
    surplus = monthly_income - monthly_expenses
    savings_rate = (surplus / monthly_income) * 100 if monthly_income > 0 else 0
    
    if surplus >= 0:
        return f"Monthly Surplus: ${surplus:,.2f}\nSavings Rate: {savings_rate:.1f}%\nAnnual Savings Potential: ${surplus * 12:,.2f}"
    else:
        return f"Monthly Deficit: ${abs(surplus):,.2f}\nYou are spending {abs(savings_rate):.1f}% more than your income.\nAnnual Shortfall: ${abs(surplus) * 12:,.2f}"
