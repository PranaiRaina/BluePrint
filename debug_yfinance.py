import yfinance as yf
from datetime import datetime, timedelta

def find_baseline_1y():
    symbol = "AAPL"
    ticker = yf.Ticker(symbol)
    
    # Fetch 1y+ data
    end_date = datetime.now()
    start_date = end_date - timedelta(days=380) # generous buffer
    hist = ticker.history(start=start_date, end=end_date, interval="1d")
    
    current_price = 258.28 
    target_percent = 7.90
    
    # target = (current - baseline) / baseline * 100
    # baseline = current / (1 + target/100)
    implied_baseline = current_price / (1 + (target_percent/100))
    print(f"Current: {current_price}, Target %: {target_percent}")
    print(f"Target Baseline Price: {implied_baseline:.2f}")
    
    print("\nSearching for matching Close price in history:")
    for index, row in hist.iterrows():
        close_price = row['Close']
        diff = abs(close_price - implied_baseline)
        if diff < 2.0: # Wider tolerance
            print(f"Date: {index.date()} | Close: {close_price:.2f} | Diff: {diff:.4f}")

    print("\n--- First 5 rows of fetched data ---")
    print(hist.head())

if __name__ == "__main__":
    find_baseline_1y()
