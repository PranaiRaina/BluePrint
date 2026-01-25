"""Time Value of Money calculation tools."""

from CalcAgent.tools.wolfram import query_wolfram


async def calculate_future_value(present_value: float, annual_rate: float, years: int) -> str:
    """
    Calculate the future value of a present investment with compound interest.
    
    Args:
        present_value: The current amount of money (principal)
        annual_rate: Annual interest rate as a percentage (e.g., 7 for 7%)
        years: Number of years for the investment
    
    Returns:
        The future value calculation result from Wolfram Alpha
    """
    query = f"future value of ${present_value:,.2f} at {annual_rate}% annual interest for {years} years"
    return await query_wolfram(query)


async def calculate_present_value(future_value: float, annual_rate: float, years: int) -> str:
    """
    Calculate the present value needed to reach a future amount.
    
    Args:
        future_value: The target future amount
        annual_rate: Annual interest rate as a percentage (e.g., 7 for 7%)
        years: Number of years until the future value is needed
    
    Returns:
        The present value calculation result from Wolfram Alpha
    """
    query = f"present value of ${future_value:,.2f} at {annual_rate}% annual interest for {years} years"
    return await query_wolfram(query)


async def calculate_loan_payment(principal: float, annual_rate: float, years: int) -> str:
    """
    Calculate the monthly payment for a loan.
    
    Args:
        principal: The loan amount
        annual_rate: Annual interest rate as a percentage (e.g., 6.5 for 6.5%)
        years: Loan term in years
    
    Returns:
        The monthly payment calculation result from Wolfram Alpha
    """
    query = f"monthly payment for ${principal:,.2f} loan at {annual_rate}% annual interest for {years} years"
    return await query_wolfram(query)
