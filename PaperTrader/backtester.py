import pandas as pd
import yfinance as yf
import json
from datetime import datetime
import asyncio

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


    def stream_llm_simulation(self, ticker, days=30, interval="1d"):
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
        
        try:
            # Fetch data
            df = yf.download(ticker, period=f"{days}d", interval=interval, progress=False)
            if df.empty:
                yield {"type": "error", "message": "No data found"}
                return
            
            # Fix YFinance MultiIndex
            if isinstance(df.columns, pd.MultiIndex):
                try:
                    df = df.xs(ticker, axis=1, level=1)
                except KeyError:
                    df.columns = df.columns.droplevel(1)
            
            total_candles = len(df)
            yield {"type": "log", "message": f"⚡ Running AI Simulation on {total_candles} candles..."}
            
            # OpenAI Client
            from openai import OpenAI
            import os
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

                # Construct Prompt
                prev_close = float(df['Close'].iloc[df.index.get_loc(index)-1]) if df.index.get_loc(index) > 0 else current_price
                price_change = current_price - prev_close
                pct_change = (price_change / prev_close) * 100

                prompt = f"""
                You are a PROFESSIONAL algorithmic trader. Your goal is CONSTANT PROFIT with MANAGED RISK.
                Be decisive but prudent.
                Context:
                - Ticker: {ticker}
                - Date: {timestamp}
                - Current Price: ${current_price:.2f}
                - Previous Close: ${prev_close:.2f} (Change: {pct_change:.2f}%)
                - Your Cash: ${self.portfolio.cash:.2f}
                - Your Position: {self.portfolio.positions.get(ticker, 0)} shares
                Strategy:
                - BUY if trend is clearly UP or significant dip > 2%.
                - SELL if you have profit > 1.5% or need to stop loss.
                - HOLD if price change is small (< 0.5%) or trend is unclear.
                Decision:
                Do you BUY, SELL, or HOLD?
                Reply in JSON: {{"action": "BUY/SELL/HOLD", "quantity": <int>, "reasoning": "<short_explanation_max_10_words>"}}
                """
                
                try:
                    response = client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        response_format={"type": "json_object"}
                    )
                    decision_str = response.choices[0].message.content
                    if decision_str.strip().startswith("```"):
                         decision_str = decision_str.strip().split("\n", 1)[-1].rsplit("\n", 1)[0]
                    
                    try:
                        decision = json.loads(decision_str)
                    except json.JSONDecodeError:
                         decision = {}
                    
                    action = decision.get("action", "HOLD").upper()
                    qty = float(decision.get("quantity", 0))
                    reasoning = decision.get("reasoning", "No reasoning provided")
                    
                    yield {"type": "log", "message": f"🤖 AI Decision: {decision_str}"}

                    if action == "BUY" and qty > 0:
                        self.portfolio.buy(ticker, current_price, qty, timestamp, reasoning)
                        msg = f"🟢 {timestamp}: Bought {qty} @ {current_price} | {reasoning}"
                        yield {"type": "log", "message": msg}
                        yield {"type": "trade", "data": {"action": "BUY", "qty": qty, "price": current_price, "reasoning": reasoning, "time": str(timestamp)}}
                        
                    elif action == "SELL" and qty > 0:
                        self.portfolio.sell(ticker, current_price, qty, timestamp, reasoning)
                        msg = f"🔴 {timestamp}: Sold {qty} @ {current_price} | {reasoning}"
                        yield {"type": "log", "message": msg}
                        yield {"type": "trade", "data": {"action": "SELL", "qty": qty, "price": current_price, "reasoning": reasoning, "time": str(timestamp)}}
                        
                except Exception as e:
                    yield {"type": "log", "message": f"⚠️ Agent Error: {e}"}
                
                # Rate Limit Protection
                import time
                time.sleep(1) # Reduced to 1s for better UX

            # Final stats
            final_equity = self.portfolio.equity_curve[-1]['equity'] if self.portfolio.equity_curve else 100000.0
            
            result_payload = {
                "initial_cash": 100000.0,
                "final_equity": final_equity,
                "return_pct": (final_equity - 100000) / 1000,
                "trades": len(self.portfolio.history),
                "history": self.portfolio.history,
                "equity_curve": [
                    {"time": str(x['time']), "value": x['equity']} for x in self.portfolio.equity_curve
                ]
            }
            yield {"type": "result", "data": result_payload}

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
