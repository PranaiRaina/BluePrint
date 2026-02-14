
import sys
import os
import pandas as pd
from datetime import datetime

# Add project root to path
sys.path.append(os.getcwd())

try:
    from PaperTrader.adapters.mock_tools import MarketDataTool, FundamentalsTool, TavilySearchTool, SimulatedAccountTool
    print("Successfully imported mock_tools")
except ImportError as e:
    print(f"Failed to import mock_tools: {e}")
    sys.exit(1)
except IndentationError as e:
    print(f"IndentationError during import: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Error during import: {e}")
    sys.exit(1)

def test_market_data_tool():
    print("\nTesting MarketDataTool...")
    try:
        data = {
            "Open": [100.0, 101.0, 102.0],
            "High": [105.0, 106.0, 107.0],
            "Low": [95.0, 96.0, 97.0],
            "Close": [102.0, 103.0, 104.0],
            "Volume": [1000, 1100, 1200]
        }
        df = pd.DataFrame(data, index=pd.to_datetime(["2023-01-01", "2023-01-02", "2023-01-03"]))
        tool = MarketDataTool(df, "TEST")
        tool.set_current_date(datetime(2023, 1, 2))
        price = tool.get_price()
        print(f"Price: {price}")
    except Exception as e:
        print(f"MarketDataTool Error: {e}")

def test_fundamentals_tool():
    print("\nTesting FundamentalsTool...")
    try:
        tool = FundamentalsTool("TEST")
        # setting api key to None to trigger the line with error if env var is missing/present
        # but the error is syntax error so import should fail first
        print("FundamentalsTool initialized")
    except Exception as e:
        print(f"FundamentalsTool Error: {e}")

def test_tavily_search_tool():
    print("\nTesting TavilySearchTool...")
    try:
        # Mock the cache file path to avoid permission issues or side effects
        tool = TavilySearchTool(api_key="TEST_KEY") 
        tool.set_current_date(datetime(2023, 1, 1))
        
        # Manually injecting a result to test date parsing helper logic 
        # (simulating internal logic since we can't easily mock the API call without more code)
        # But we can test the _load_cache/save_cache at least
        print("TavilySearchTool initialized")
    except Exception as e:
        print(f"TavilySearchTool Error: {e}")

if __name__ == "__main__":
    test_market_data_tool()
    test_fundamentals_tool()
    test_tavily_search_tool()
