from mcp.server.fastmcp import FastMCP
from PaperTrader.service import paper_trading_service

# Create an MCP Server named "PaperTrader"
mcp = FastMCP("PaperTrader")

@mcp.tool()
async def get_my_portfolio(user_id: str = "00000000-0000-0000-0000-000000000000"):
    """
    Get the summary and holdings of the default portfolio for the user.
    Returns cash balance, total equity, and a list of active positions (ticker, quantity, current value).
    """
    try:
        # Check if user has a portfolio, if not create one
        portfolios = paper_trading_service.get_portfolios(user_id)
        if not portfolios:
            paper_trading_service.create_portfolio(user_id, "AI Managed Portfolio")
            portfolios = paper_trading_service.get_portfolios(user_id)
        
        portfolio_id = portfolios[0]['id']
        return paper_trading_service.get_portfolio_details(user_id, portfolio_id)
    except Exception as e:
        return f"Error fetching portfolio: {str(e)}"

@mcp.tool()
async def get_ticker_price(ticker: str) -> float:
    """
    Get the current price of a US stock ticker using Hybrid (Finnhub/YFinance) data.
    """
    return paper_trading_service.get_price(ticker)

@mcp.tool()
async def buy_stock(ticker: str, quantity: float, reason: str = "Strategy"):
    """
    Buy a specific quantity of a US stock.
    Args:
        ticker: The stock symbol (e.g., AAPL).
        quantity: Number of shares to buy.
        reason: The strategic reason for this trade (logged for transparency).
    """
    try:
        user_id = "00000000-0000-0000-0000-000000000000" # TODO: MCP Context injection
        
        # Get Default Portfolio
        portfolios = paper_trading_service.get_portfolios(user_id)
        if not portfolios:
            return "Error: No portfolio found."
        portfolio_id = portfolios[0]['id']
        
        result = paper_trading_service.execute_trade(user_id, portfolio_id, ticker, "BUY", quantity)
        return {
            "status": "success", 
            "message": f"Bought {quantity} shares of {ticker} at ${result['price_per_share']}",
            "trade_details": result
        }
    except Exception as e:
        return f"Trade Failed: {str(e)}"

@mcp.tool()
async def sell_stock(ticker: str, quantity: float, reason: str = "Strategy"):
    """
    Sell a specific quantity of a US stock.
    Args:
        ticker: The stock symbol (e.g., AAPL).
        quantity: Number of shares to sell.
        reason: The strategic reason for this trade.
    """
    try:
        user_id = "00000000-0000-0000-0000-000000000000"
        
        portfolios = paper_trading_service.get_portfolios(user_id)
        if not portfolios:
            return "Error: No portfolio found."
        portfolio_id = portfolios[0]['id']
        
        result = paper_trading_service.execute_trade(user_id, portfolio_id, ticker, "SELL", quantity)
        return {
            "status": "success", 
            "message": f"Sold {quantity} shares of {ticker} at ${result['price_per_share']}",
            "trade_details": result
        }
    except Exception as e:
        return f"Trade Failed: {str(e)}"

if __name__ == "__main__":
    mcp.run()
