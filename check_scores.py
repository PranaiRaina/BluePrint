import asyncio
import os
import sys

# Add the project root to sys.path
sys.path.append(os.getcwd())

from StockAgents.services.finnhub_client import finnhub_client

async def check():
    tickers = ["CAL", "EQH", "DDL", "NTLA", "NVAX", "CLSK", "IOVA", "SOUN", "RXRX", "HIMS", "UAA", "AI", "APLD"]
    print(f"{'Ticker':<10} {'Score':<10} {'Recommendation':<15}")
    print("-" * 35)
    for ticker in tickers:
        try:
            res = await finnhub_client.get_analyst_ratings(ticker)
            if "error" in res:
                print(f"{ticker:<10} {'Error':<10} {res['error']}")
            else:
                print(f"{ticker:<10} {res['consensusScore']:<10} {res['recommendation']}")
        except Exception as e:
            print(f"{ticker:<10} {'Error':<10} {str(e)}")

if __name__ == "__main__":
    asyncio.run(check())
asyncio.run(finnhub_client.get_analyst_ratings("PARA"))
