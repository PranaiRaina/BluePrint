
import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
symbol = "AAPL"

if not api_key:
    print("❌ ERROR: ALPHA_VANTAGE_API_KEY not found in .env")
else:
    # Adding source=trading_agents as requested
    url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={symbol}&apikey={api_key}&source=trading_agents"
    response = requests.get(url)
    data = response.json()
    
    if "Symbol" in data:
        print(f"✅ SUCCESS: Alpha Vantage API is working with source tag. Retreived data for {data['Symbol']}")
    elif "Note" in data and "rate limit" in data["Note"].lower():
        print("⚠️ WARNING: API key is working but you have hit the RATE LIMIT.")
    elif "Information" in data:
        print(f"⚠️ API INFO: {data['Information']}")
    else:
        print(f"❌ FAILURE: API responded but data is missing or invalid. Response: {data}")
