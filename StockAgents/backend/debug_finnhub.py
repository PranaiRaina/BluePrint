import httpx
import asyncio
import os
import time

# Create a dummy settings object or valid key
API_KEY = "d5qo68pr01qhn30gtq1gd5qo68pr01qhn30gtq20" # Hardcoded from user prompt for debug

async def test_candles():
    to_ts = int(time.time())
    from_ts = to_ts - (60 * 24 * 60 * 60) # 60 days
    # For intraday, maybe 1 day?
    from_ts_intra = to_ts - (24 * 60 * 60)

    async with httpx.AsyncClient() as client:
        # Test 1: Daily
        print("--- Testing Daily Candles (D) ---")
        params = {
            "symbol": "AAPL",
            "resolution": "D",
            "from": from_ts,
            "to": to_ts,
            "token": API_KEY
        }
        resp = await client.get("https://finnhub.io/api/v1/stock/candle", params=params)
        print(f"Status: {resp.status_code}")
        data = resp.json()
        if "s" in data and data["s"] == "ok":
            print(f"Success! Got {len(data.get('c', []))} candles.")
            print(f"Last candle: {data.get('c', [])[-1]}")
        else:
            print(f"Failed/No Data: {data}")

        # Test 2: 5 Minute
        print("\n--- Testing 5-Min Candles (5) ---")
        params_5 = {
            "symbol": "AAPL",
            "resolution": "5",
            "from": from_ts_intra,
            "to": to_ts,
            "token": API_KEY
        }
        resp_5 = await client.get("https://finnhub.io/api/v1/stock/candle", params=params_5)
        print(f"Status: {resp_5.status_code}")
        data_5 = resp_5.json()
        if "s" in data_5 and data_5["s"] == "ok":
            print(f"Success! Got {len(data_5.get('c', []))} candles.")
        else:
            print(f"Failed/No Data: {data_5}")

if __name__ == "__main__":
    asyncio.run(test_candles())
