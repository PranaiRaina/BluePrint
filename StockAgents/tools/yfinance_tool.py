"""
yfinance Tool - Historical Price Data (Secondary Data Source)

Used for:
- Fetching historical price data for volatility calculation
- No API key required

Note: Finnhub remains the PRIMARY source for real-time quotes.
"""

import yfinance as yf
from datetime import datetime, timedelta


def get_historical_prices(ticker: str, days: int = 90) -> dict:
    """
    Fetches historical daily closing prices from Yahoo Finance.

    Args:
        ticker: Stock ticker symbol
        days: Number of days of history to fetch

    Returns:
        {ticker, prices: [...], dates: [...], count: int}
    """
    try:
        ticker = ticker.upper().strip()

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        # Fetch data
        stock = yf.Ticker(ticker)
        hist = stock.history(start=start_date, end=end_date)

        if hist.empty:
            return {"error": "No historical data found", "ticker": ticker}

        # Extract closing prices
        close_prices = hist["Close"].tolist()
        dates = [d.strftime("%Y-%m-%d") for d in hist.index]

        return {
            "ticker": ticker,
            "prices": close_prices,
            "dates": dates,
            "count": len(close_prices),
            "source": "yfinance",
        }

    except Exception as e:
        return {"error": f"yfinance error: {str(e)}", "ticker": ticker}
