import asyncio
import sys
import os

# Ensure we can import from project root
sys.path.append(os.getcwd())

from ManagerAgent.api import run_backtest

async def test_api():
    print("Testing /api/backtest logic...")
    request = {"ticker": "NVDA", "days": 5}
    try:
        result = await run_backtest(request)
        print("Success!")
        print(f"Final Equity: {result['final_equity']}")
        print(f"Trades: {result['trades']}")
        print(f"Return: {result['return_pct']}%")
        
        if result['trades'] > 0:
             print("Sample Trade:", result['trade_log'][0])
             
    except Exception as e:
        print(f"API Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_api())
