import os
import json
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PaperTrader.TradingAgents.dataflows.alpha_vantage_fundamentals import get_fundamentals

def test_historical_isolation():
    load_dotenv()
    
    ticker = "AAPL"
    # Choose a date in the past (e.g., 2021)
    past_date = "2021-01-05"
    
    print(f"--- Testing Historical Isolation for {ticker} on {past_date} ---")
    
    # 1. Get Live Data (for comparison)
    live_data_str = get_fundamentals(ticker)
    live_data = json.loads(live_data_str)
    live_pe = live_data.get("PERatio")
    live_mc = live_data.get("MarketCapitalization")
    
    print(f"Live P/E: {live_pe}")
    print(f"Live Market Cap: {live_mc}")
    
    # 2. Get Historical Data (isolated)
    hist_data_str = get_fundamentals(ticker, curr_date=past_date)
    hist_data = json.loads(hist_data_str)
    hist_pe = hist_data.get("PERatio")
    hist_mc = hist_data.get("MarketCapitalization")
    note = hist_data.get("Note")
    
    print(f"\nHistorical P/E ({past_date}): {hist_pe}")
    print(f"Historical Market Cap ({past_date}): {hist_mc}")
    print(f"Note: {note}")
    
    # Validation
    if hist_pe != live_pe and note and "reconstructed" in note:
        print("\n✅ SUCCESS: Historical isolation confirmed. P/E was overridden.")
    else:
        print("\n❌ FAILURE: Data was not overridden or ratios matched live exactly.")

if __name__ == "__main__":
    test_historical_isolation()
