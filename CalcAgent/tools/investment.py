"""Investment calculation tools."""

from CalcAgent.tools.wolfram import query_wolfram


async def calculate_compound_interest(principal: float, annual_rate: float, years: int, compounds_per_year: int = 12) -> str:
    """
    Calculate compound interest over time.
    
    Args:
        principal: Initial investment amount
        annual_rate: Annual interest rate as a percentage (e.g., 5 for 5%)
        years: Number of years
        compounds_per_year: How often interest compounds (12 for monthly, 4 for quarterly, 1 for annually)
    
    Returns:
        The compound interest calculation result from Wolfram Alpha
    """
    query = f"compound interest on ${principal:,.2f} at {annual_rate}% for {years} years compounded {compounds_per_year} times per year"
    return await query_wolfram(query)


async def calculate_roi(initial_investment: float, final_value: float, years: int) -> str:
    """
    Calculate Return on Investment (ROI) and annualized return.
    
    Args:
        initial_investment: The original investment amount
        final_value: The ending value of the investment
        years: Number of years the investment was held
    
    Returns:
        ROI calculation including annualized return from Wolfram Alpha
    """
    total_roi = ((final_value - initial_investment) / initial_investment) * 100
    query = f"annualized return for investment growing from ${initial_investment:,.2f} to ${final_value:,.2f} over {years} years"
    wolfram_result = await query_wolfram(query)
    return f"Total ROI: {total_roi:.2f}%\n\n{wolfram_result}"
