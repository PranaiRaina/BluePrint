import asyncio
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("FINNHUB_API_KEY")
print(f"Testing API Key: {API_KEY[:4]}...{API_KEY[-4:] if API_KEY and len(API_KEY)>4 else '****'}")

async def check_key():
    if not API_KEY:
        print("❌ Error: FINNHUB_API_KEY not found in environment.")
        return

    url = "https://finnhub.io/api/v1/quote"
    params = {"symbol": "AAPL", "token": API_KEY}
    
    print("\nAttempting to fetch quote for AAPL...")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params)
            
            print(f"Status Code: {resp.status_code}")
            
            if resp.status_code == 200:
                print("✅ Success! The API key is valid and working.")
                print(f"Response: {resp.json()}")
            elif resp.status_code == 429:
                print("⚠️  Rate Limit Exceeded (429). The key is valid, but you have hit the usage limit.")
                print(f"Headers: {resp.headers}")
            elif resp.status_code == 401:
                print("❌ Unauthorized (401). The API key is invalid.")
            else:
                print(f"❌ Unknown Error: {resp.text}")
                
    except Exception as e:
        print(f"❌ Connection Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_key())
