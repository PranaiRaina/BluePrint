"""
Test script for RP Trader Adapter
Runs Warren on a month of WMT data to verify the integration works.
"""

import asyncio
# import yfinance as yf (Removed)
import pandas as pd
from datetime import datetime, timedelta
import json
import os
import sys

# Ensure path is set up
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from PaperTrader.adapters import create_rp_trader, STRATEGIES


async def test_warren_on_wmt():
    """Test Warren Patience on 1 month of WMT data."""
    print("=" * 60)
    print("RP TRADER ADAPTER TEST: Warren on WMT")
    print("=" * 60)

    # Download historical data via Alpha Vantage
    ticker = "WMT"
    print(f"\n📥 Downloading {ticker} data from Alpha Vantage...")
    
    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        print("❌ ALPHA_VANTAGE_API_KEY not found in environment")
        return

    import requests
    from io import StringIO
    
    # Use TIME_SERIES_DAILY for daily data
    url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&apikey={api_key}&outputsize=compact&datatype=csv&source=trading_agents"
    
    try:
        r = requests.get(url)
        if "Error Message" in r.text or "Information" in r.text:
            print(f"❌ Alpha Vantage API Error: {r.text}")
            return
            
        # Parse CSV to DataFrame
        # Data comes as: timestamp,open,high,low,close,volume
        df = pd.read_csv(StringIO(r.text), index_col="timestamp", parse_dates=True)
        df.index.name = "Date"
        df = df.sort_index() # Sort ascending
        
        # Renaissance renaming (AV uses lowercase, we expect Title Case)
        df = df.rename(columns={
            "open": "Open",
            "high": "High",
            "low": "Low",
            "close": "Close",
            "volume": "Volume"
        })
        
        # Filter for last 60 days
        df = df.tail(60)
        
    except Exception as e:
        print(f"❌ Failed to download data: {e}")
        return

    print(f"✅ Downloaded {len(df)} rows of data")
    print(f"   Date range: {df.index[0].date()} to {df.index[-1].date()}")

    # Create Warren
    print(f"\n🤵 Creating Warren (Value Investor)...")
    print(f"   Strategy: {STRATEGIES['Warren'][:100]}...")
    
    warren = create_rp_trader(
        name="Warren",
        df=df,
        ticker=ticker,
        model_name="gemini-2.5-flash",
        initial_balance=10000.0,
    )

    # Pick a few dates to test (not every day to save API calls)
    test_dates = df.index[-5:]  # Last 5 trading days
    print(f"\n📅 Testing on {len(test_dates)} dates")

    for date in test_dates:
        print(f"\n{'='*40}")
        print(f"📆 Date: {date}")
        print("-" * 40)
        
        try:
            result = await warren.step(datetime.combine(date.date(), datetime.min.time()))
            
            print(f"💬 Output: {result.get('output', 'No output')[:200]}...")
            print(f"💰 Portfolio: ${result['portfolio']['total_equity']:.2f}")
            print(f"📈 P&L: ${result['portfolio']['pnl']:.2f} ({result['portfolio']['pnl_percent']:.2f}%)")
            
            if result.get('transactions_today'):
                print(f"🔄 Trades today: {len(result['transactions_today'])}")
                for tx in result['transactions_today']:
                    print(f"   - {tx['action']} {tx['quantity']} shares at ${tx['price']:.2f}")
        except Exception as e:
            print(f"❌ Error: {e}")

    # Final summary
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    summary = warren.get_summary()
    print(f"Trader: {summary['name']}")
    print(f"Initial Balance: ${summary['initial_balance']:.2f}")
    print(f"Final Equity: ${summary['final_equity']:.2f}")
    print(f"P&L: ${summary['pnl']:.2f} ({summary['pnl_percent']:.2f}%)")
    print(f"Total Trades: {summary['total_trades']}")
    
    if summary['transactions']:
        print("\nAll Transactions:")
        for tx in summary['transactions']:
            print(f"  {tx['timestamp']}: {tx['action']} {tx['quantity']} {tx['ticker']} @ ${tx['price']:.2f}")
            print(f"    Rationale: {tx.get('rationale', 'N/A')[:100]}...")


if __name__ == "__main__":
    asyncio.run(test_warren_on_wmt())
