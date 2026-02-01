import os
import requests
from dotenv import load_dotenv

load_dotenv()


# --- Finnhub Test ---
def test_finnhub():
    print("\n--- Testing Finnhub API ---")
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        print("❌ FINNHUB_API_KEY missing")
        return

    url = f"https://finnhub.io/api/v1/quote?symbol=AAPL&token={api_key}"
    try:
        response = requests.get(url)
        if response.status_code == 200:
            data = response.json()
            if "c" in data:
                print(f"✅ Finnhub Working. AAPL Price: {data['c']}")
            else:
                print(f"❌ Finnhub Error: Unexpected format {data}")
        elif response.status_code == 401:
            print("❌ Finnhub Error: 401 Unauthorized (Invalid Key)")
        elif response.status_code == 429:
            print("⚠️ Finnhub Error: Rate Limit Exceeded")
        else:
            print(f"❌ Finnhub Error: {response.status_code} {response.text}")
    except Exception as e:
        print(f"❌ Finnhub Connection Failed: {e}")


# --- Tavily Test ---
def test_tavily():
    print("\n--- Testing Tavily API ---")
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        print("❌ TAVILY_API_KEY missing")
        return

    url = "https://api.tavily.com/search"
    payload = {"query": "test connection", "api_key": api_key}
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("✅ Tavily Working")
        else:
            print(f"❌ Tavily Error: {response.status_code} {response.text}")
    except Exception as e:
        print(f"❌ Tavily Connection Failed: {e}")


# --- Wolfram Test ---
def test_wolfram():
    print("\n--- Testing Wolfram Alpha API ---")
    app_id = os.getenv("WOLFRAM_APP_ID")
    if not app_id:
        print("❌ WOLFRAM_APP_ID missing")
        return

    url = f"http://api.wolframalpha.com/v1/result?appid={app_id}&i=2%2B2"
    try:
        response = requests.get(url)
        if response.status_code == 200 and response.text.strip() == "4":
            print(f"✅ Wolfram Working. 2+2={response.text}")
        else:
            print(f"❌ Wolfram Error: {response.status_code} {response.text}")
    except Exception as e:
        print(f"❌ Wolfram Connection Failed: {e}")


# --- Google/Gemini Test (Using standard endpoint if possible, or skip if complex configured) ---
# Assuming usage in LangChain, but let's try a simple HTTP call if it's Gemini
def test_google():
    print("\n--- Testing Google API (Gemini) ---")
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GOOGLE_API_KEY missing")
        return

    # Use standard endpoint for simple key check if 2.0-flash is restricted,
    # but let's try 1.5-flash which is generally available if 2.0 fails
    # or just use the discovery URL style
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
    payload = {"contents": [{"parts": [{"text": "Hello"}]}]}

    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print("✅ Google Gemini Working (1.5-flash raw)")
        else:
            print(
                f"⚠️ Google GenAI Error: {response.status_code}. Trying OpenAI Compat..."
            )
            # Try OpenAI Compat style which app uses
            url_compat = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            }
            payload_compat = {
                "model": "gemini-2.0-flash",
                "messages": [{"role": "user", "content": "hi"}],
                "max_tokens": 10,
            }
            resp_compat = requests.post(
                url_compat, json=payload_compat, headers=headers
            )
            if resp_compat.status_code == 200:
                print("✅ Google Gemini Working (2.0-flash OpenAI Compat)")
            else:
                print(
                    f"❌ Google GenAI Error: {resp_compat.status_code} {resp_compat.text}"
                )

    except Exception as e:
        print(f"❌ Google Connection Failed: {e}")

if __name__ == "__main__":
    test_finnhub()
    test_tavily()
    test_wolfram()
    test_google()
