import asyncio
import os
import sys
from dotenv import load_dotenv
load_dotenv()
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "PaperTrader"))
from PaperTrader.agent_backtester import AgentBacktestEngine

async def run_test():
    print("🚀 Starting 1-Day Agent Backtest for 2026-01-27...")
    engine = AgentBacktestEngine()
    
    # We want ONLY 2026-01-27.
    # The backtester takes `days` (lookback from now or tail of data).
    # To test a SPECIFIC date, I might need to hack the backtester or just run it and filter logic.
    # Actually, the backtester downloads data dependent on Alpha Vantage.
    # If I ask for days=1, it takes the last available day from Alpha Vantage CSV.
    # Alpha Vantage CSV ends yesterday/today. 
    # To force 2026-01-27, I should modify the backtester to accept a start/end date or hack the dataframe inside.
    
    # For now, let's subclass and override the data fetching to force a single row dataframe for 2026-01-27.
    
    
    # Mock data for 1/27/2026 if AV doesn't return it exactly as last row (it might be too far back if days=1)
    # Actually 1/27/2026 is last week.
    
    # Let's try running it normally for "days=10" and see if it prints dates.
    # But user wants SPECIFICALLY 1/27.
    
    # I will create a custom test harness that manually calls stream_agent_simulation but patches requests.get
    # OR simply use the engine but modify the loop in a subclass.
    
    pass

# Simplified Approach:
# I will modify agent_backtester.py temporarily to allow passing a specific date range or just mock the data fetching for this test.
# Actually, I'll write a script that instantiates the graph and calls propagate() once for that date manually, bypassing the backtester's data fetching loop.
# This proves the "integration" logic works (graph.propagate + signal parsing).

from TradingAgents.graph.trading_graph import TradingAgentsGraph

async def run_manual_day():
    print("🧪 initializing graph...")
    graph = TradingAgentsGraph(debug=True) # Debug true to see trace!
    
    ticker = "NVDA"
    date = "2026-01-27"
    cash = 100000.0
    holdings = 0
    portfolio_value = 100000.0
    
    # Fetch actual stock price for the date
    import yfinance as yf
    stock = yf.Ticker(ticker)
    hist = stock.history(start=date, end="2026-01-28")
    if not hist.empty:
        current_price = hist['Close'].iloc[0]
    else:
        current_price = 100.0  # Fallback
    print(f"📈 Current price for {ticker} on {date}: ${current_price:.2f}")
    
    print(f"📅 Propagating for {ticker} on {date}...")
    
    try:
        final_state, signal = graph.propagate(
            company_name=ticker,
            trade_date=date,
            portfolio_cash=cash,
            current_shares=holdings,
            portfolio_value=portfolio_value,
            current_price=current_price
        )
        
        print("\n✅ Graph Execution Complete!")
        print("Signal:", signal)
        print("Final Decision Text:", final_state.get("final_trade_decision", "N/A")[:200] + "...")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(run_manual_day())
