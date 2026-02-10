import requests

BASE_URL = "http://localhost:8001"
USER_ID = "00000000-0000-0000-0000-000000000000"

def test_toggle():
    print(f"Testing Toggle on {BASE_URL}...")
    
    # 1. Get Portfolio ID
    try:
        res = requests.get(f"{BASE_URL}/paper-trader/portfolios?user_id={USER_ID}")
        portfolios = res.json()
        if not portfolios:
            print("No portfolios found.")
            return
        
        pid = portfolios[0]['id']
        print(f"Found Portfolio: {pid}")
        
        # 2. Toggle ON
        print("Toggling ON...")
        res = requests.patch(f"{BASE_URL}/api/portfolios/{pid}/toggle", json={"is_active": True})
        
        if res.status_code == 200:
            print("✅ Toggle ON Success:", res.json())
        else:
            print(f"❌ Toggle OFF Failed: {res.status_code}")
            print(res.text)

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_toggle()
