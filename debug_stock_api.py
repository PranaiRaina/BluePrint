
import requests
import json
import os

def check_stock_data():
    # Try to find a valid token if possible, or assume no auth for this test if middleware allows (it might fail 401)
    # But user logs showed 200 OK for OPTIONS/GET, so presumably auth is working or not enforced strictly for localhost?
    # Wait, logs definitely showed 401 earlier, but then 200 OK in the latest block.
    # We will try to grab token from local_store.json if it exists, but previous attempts failed.
    # Let's try without header first, simply to see if we can reach it.
    
    url = "http://localhost:8001/v1/agent/stock/AAPL?time_range=1y"
    
    # Attempt to read token from frontend local storage dump if any... unlikely.
    # Let's just run it. If 401, we know we need auth.
    try:
        print(f"Fetching {url}...")
        resp = requests.get(url, timeout=5)
        print(f"Status: {resp.status_code}")
        
        if resp.status_code == 200:
            data = resp.json()
            candles = data.get("candles", [])
            print(f"Candles Count: {len(candles)}")
            if candles:
                print("First 3 candles:", json.dumps(candles[:3], indent=2))
                print("Last 3 candles:", json.dumps(candles[-3:], indent=2))
                
                # Verify format
                sample = candles[0]
                if "time" not in sample or "value" not in sample:
                    print("ERROR: Missing 'time' or 'value' formatted correctly in candles.")
                else:
                    print("SUCCESS: Data structure seems valid.")
            else:
                print("WARNING: Candles array is empty.")
        else:
            print("Response:", resp.text)
            
    except Exception as e:
        print(f"Request failed: {e}")

if __name__ == "__main__":
    check_stock_data()
