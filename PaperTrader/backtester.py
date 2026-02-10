import pandas as pd
import requests
import json
import asyncio
import os
from io import StringIO

# Mock Portfolio for Backtesting
class MockPortfolio:
    def __init__(self, initial_cash=100000.0):
        self.cash = initial_cash
        self.positions = {} # {ticker: qty}
        self.history = []
        self.equity_curve = []

    def buy(self, ticker, price, qty, timestamp, reasoning=""):
        cost = price * qty
        if self.cash >= cost:
            self.cash -= cost
            self.positions[ticker] = self.positions.get(ticker, 0) + qty
            self.history.append({
                "time": str(timestamp), "action": "BUY", "ticker": ticker, 
                "price": price, "qty": qty, "reasoning": reasoning
            })
            return True
        return False

    def sell(self, ticker, price, qty, timestamp, reasoning=""):
        current_qty = self.positions.get(ticker, 0)
        if current_qty >= qty:
            revenue = price * qty
            self.cash += revenue
            self.positions[ticker] -= qty
            self.history.append({
                "time": str(timestamp), "action": "SELL", "ticker": ticker, 
                "price": price, "qty": qty, "reasoning": reasoning
            })
            return True
        return False

    def update_equity(self, current_prices, timestamp):
        equity = self.cash
        for ticker, qty in self.positions.items():
            if qty > 0:
                equity += qty * current_prices.get(ticker, 0)
        self.equity_curve.append({"time": str(timestamp), "equity": equity})

# The Backtester Engine
class BacktestEngine:
    def __init__(self, agent_logic_func):
        """
        agent_logic_func: function(context) -> action
        """
        self.agent = agent_logic_func
        self.portfolio = MockPortfolio()


    async def stream_llm_simulation(self, ticker, days=30, interval="1d"):
        """
        Generator that yields real-time events from the simulation.
        Yields JSON-serializable dicts:
        - {"type": "log", "message": "..."}
        - {"type": "progress", "current": i, "total": n}
        - {"type": "decision", "data": {...}}
        - {"type": "trade", "data": {...}} 
        - {"type": "result", "data": {...}}
        """
        yield {"type": "log", "message": f"📉 Fetching {days}d history for {ticker} ({interval})..."}
        
        # Alpha Vantage Download
        api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        if not api_key:
            yield {"type": "error", "message": "ALPHA_VANTAGE_API_KEY not found"}
            return

        # Use TIME_SERIES_DAILY for now (supports interval=Daily only reliably on free tier)
        # Note: 'interval' arg is ignored here as we hardcode daily for stability
        url = f"https://www.alphavantage.co/query?function=TIME_SERIES_DAILY&symbol={ticker}&apikey={api_key}&outputsize=compact&datatype=csv"
        
        try:
            r = requests.get(url)
            if "Error Message" in r.text or "Information" in r.text:
                yield {"type": "error", "message": f"Alpha Vantage Error: {r.text[:100]}..."}
                return
                
            # Parse CSV to DataFrame
            df = pd.read_csv(StringIO(r.text), index_col="timestamp", parse_dates=True)
            df.index.name = "Date"
            df = df.sort_index() # Sort ascending
            
            # Renaissance renaming
            df = df.rename(columns={
                "open": "Open", 
                "high": "High", 
                "low": "Low", 
                "close": "Close", 
                "volume": "Volume"
            })
            
            # Filter days
            df = df.tail(days)
            
            if df.empty:
                yield {"type": "error", "message": "No data found"}
                return

            total_candles = len(df)
            yield {"type": "log", "message": f"⚡ Running AI Simulation on {total_candles} candles..."}
            
            # OpenAI Client
            from openai import OpenAI

            from pathlib import Path
            from dotenv import load_dotenv

            env_path = Path(__file__).resolve().parent.parent / '.env'
            load_dotenv(dotenv_path=env_path)
            
            google_key = os.getenv("GOOGLE_API_KEY")
            if not google_key:
                yield {"type": "error", "message": "GOOGLE_API_KEY not found"}
                return
                
            client = OpenAI(
                api_key=google_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
            )
            model = "gemini-2.0-flash" 

            for i, (index, row) in enumerate(df.iterrows()):
                # Context state
                current_price = float(row['Close'])
                timestamp = index
                
                # Update Portfolio Equity
                self.portfolio.update_equity({ticker: current_price}, timestamp)
                
                yield {
                    "type": "progress", 
                    "current": i + 1, 
                    "total": total_candles,
                    "date": str(timestamp), 
                    "equity": self.portfolio.equity_curve[-1]['equity']
                }

            # Initialize RP Traders
            from PaperTrader.adapters import create_rp_trader
            
            trader_names = ["George"]
            traders = []
            
            yield {"type": "log", "message": f"👥 Initializing {len(trader_names)} RP Traders..."}
            
            for name in trader_names:
                adapter = create_rp_trader(
                    name=name,
                    df=df,
                    ticker=ticker,
                    model_name="gemini-2.0-flash", # Use robust model for simulation
                    initial_balance=10000.0
                )
                traders.append(adapter)

            # Initialize Journals & Equity Curves
            journals = {t.name: [] for t in traders}
            equity_curves = {t.name: [] for t in traders}

            # --- MAIN SIMULATION LOOP ---
            for i, (index, row) in enumerate(df.iterrows()):
                current_date = index
                current_price = float(row['Close'])
                
                # yield {"type": "log", "message": f"📅 Processing {current_date.date()}..."}
                
                day_decisions = {}
                
                # Run each trader
                for trader in traders:
                    # Execute Step
                    try:
                        decision_record = await trader.step(current_date)
                        output_text = decision_record.get('output', '')
                        
                        # Capture Equity for Curve
                        current_equity = trader.account.get_portfolio_value()['total_equity']
                        equity_curves[trader.name].append({
                            "time": str(current_date),
                            "equity": current_equity
                        })
                        
                        # Log Decision
                        yield {
                            "type": "decision", 
                            "data": {
                                "trader": trader.name,
                                "date": str(current_date),
                                "output": output_text,
                                "portfolio": decision_record['portfolio']
                            }
                        }
                        
                        # Process and Log Actions
                        txs = decision_record.get('transactions_today', [])
                        
                        if txs:
                            # 1. Log Trades
                            for tx in txs:
                                journal_entry = {
                                    "action": tx['action'],
                                    "qty": tx['quantity'], 
                                    "price": tx['price'], 
                                    "reasoning": tx.get('rationale', ''), 
                                    "time": str(current_date.date()) 
                                }
                                journals[trader.name].append(journal_entry)
                                
                                yield {
                                    "type": "trade", 
                                    "data": {
                                        "trader": trader.name,
                                        "action": tx['action'],
                                        "qty": tx['quantity'], 
                                        "price": tx['price'], 
                                        "reasoning": tx.get('rationale', ''), 
                                        "time": str(current_date)
                                    }
                                }
                                msg = f"{trader.name}: {tx['action']} {tx['quantity']} @ {tx['price']:.2f}"
                                yield {"type": "log", "message": msg}
                        else:
                            # 2. Log HOLD / No Trade
                            rationale = decision_record.get('rationale') or "No trade action taken."
                            journal_entry = {
                                "action": "HOLD",
                                "qty": 0, 
                                "price": current_price, 
                                "reasoning": rationale, 
                                "time": str(current_date.date()) 
                            }
                            journals[trader.name].append(journal_entry)
                            
                            # Stream Log
                            msg = f"{trader.name}: HOLD @ {str(current_date.date())} | {rationale[:100]}..."
                            yield {"type": "log", "message": msg}
                                
                    except Exception as e:
                        yield {"type": "log", "message": f"❌ Error running {trader.name}: {e}"}

                # Progress Update
                yield {
                    "type": "progress", 
                    "current": i + 1, 
                    "total": total_candles,
                    "date": str(current_date), 
                    # Use accurate average equity
                    "equity": sum([t.account.get_portfolio_value()['total_equity'] for t in traders]) / len(traders)
                }
                
                # Tiny sleep to allow UI to render (simulated latency)
                await asyncio.sleep(0.01)

            # --- FINAL RESULTS ---
            final_results = []
            for trader in traders:
                summary = trader.get_summary()
                
                final_results.append({
                    "name": trader.name,
                    "initial_cash": summary['initial_balance'],
                    "final_equity": summary['final_equity'],
                    "return_pct": summary['pnl_percent'],
                    "trades": summary['total_trades'],
                    "history": journals[trader.name], 
                    "equity_curve": equity_curves[trader.name] # Use accurate curve
                })
            
            yield {"type": "result", "data": final_results}


        except Exception as e:
            yield {"type": "error", "message": str(e)}

    def run_llm_simulation(self, ticker, days=30, interval="1d"):
        """
        Legacy wrapper that consumes the stream and returns the final result.
        """
        final_result = {}
        for event in self.stream_llm_simulation(ticker, days, interval):
            if event["type"] == "result":
                final_result = event["data"]
            elif event["type"] == "error":
                return {"error": event["message"]}
        return final_result

if __name__ == "__main__":
    # Test Run
    engine = BacktestEngine(None)
    result = engine.run_llm_simulation("NVDA", days=5)
    print(json.dumps(result, indent=2, default=str))
