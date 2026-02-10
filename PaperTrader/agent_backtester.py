import yfinance as yf
import asyncio
import os
import sys
from dotenv import load_dotenv

# Load Env Vars FIRST
load_dotenv()

# Add PaperTrader to path so TradingAgents internal imports work correctly
_paper_trader_path = os.path.dirname(os.path.abspath(__file__))
if _paper_trader_path not in sys.path:
    sys.path.insert(0, _paper_trader_path)

# Import the TradingAgentsGraph
from TradingAgents.graph.trading_graph import TradingAgentsGraph

# Reuse MockPortfolio from existing backtester if possible, or redefine it here to be self-contained
# For stability, I will redefine a clean version here.

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
    
    def get_portfolio_value(self, current_prices):
        equity = self.cash
        for ticker, qty in self.positions.items():
            if qty > 0:
                equity += qty * current_prices.get(ticker, 0)
        return equity

class AgentBacktestEngine:
    def __init__(self):
        # Instantiate the Agent Graph ONCE to persist memory
        print("🤖 Initializing Trading Agents Graph...")
        self.graph = TradingAgentsGraph(debug=False)
        self.portfolio = MockPortfolio()

    async def stream_agent_simulation(self, ticker, days=30, interval="1d"):
        """
        Generator that yields real-time events from the simulation using the AI Agent.
        """
        yield {"type": "log", "message": f"📉 Fetching {days}d history for {ticker}..."}
        
        # Fetch history via yfinance (more reliable, no rate limits for basic history)
        try:
            ticker_obj = yf.Ticker(ticker.upper())
            # Fetch slightly more days to ensure we have enough post-filtering
            df = ticker_obj.history(period=f"{days * 2}d")
            
            if df.empty:
                yield {"type": "error", "message": f"yfinance Error: No data found for {ticker}"}
                return
            
            # Keep index as is (Date) but localize to none for consistency
            if df.index.tz is not None:
                df.index = df.index.tz_localize(None)
            
            # Filter to requested tail
            df = df.tail(days)
            
            if df.empty:
                yield {"type": "error", "message": "No data found after filtering"}
                return

            total_candles = len(df)
            yield {"type": "log", "message": f"⚡ Running Agent Strategy on {total_candles} candles..."}
            
            # --- MAIN SIMULATION LOOP ---
            
            journals = []
            
            for i, (index, row) in enumerate(df.iterrows()):
                current_date = index.strftime("%Y-%m-%d")
                current_price = float(row['Close'])
                
                # Context Values
                current_holdings = self.portfolio.positions.get(ticker, 0)
                current_cash = self.portfolio.cash
                # Estimate portfolio value for prompt context
                current_equity = self.portfolio.get_portfolio_value({ticker: current_price})
                
                yield {"type": "log", "message": "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"}
                yield {"type": "log", "message": f"📅 Day {i+1}/{total_candles} | {current_date} | ${ticker} @ ${current_price:.2f}"}
                yield {"type": "log", "message": f"💼 Portfolio: Cash ${current_cash:,.0f} | Holdings {current_holdings} shares | Equity ${current_equity:,.0f}"}

                # Invoke the Agent Graph with step-by-step progress
                try:
                    final_state = None
                    signal = None
                    
                    for step_name, is_final, state, sig in self.graph.propagate_with_steps(
                        company_name=ticker,
                        trade_date=current_date,
                        portfolio_cash=current_cash,
                        current_shares=current_holdings,
                        portfolio_value=current_equity,
                        current_price=current_price
                    ):
                        # Yield the current agent step to the UI
                        yield {"type": "log", "message": f"  {step_name}"}
                        await asyncio.sleep(0)  # Allow UI to update
                        
                        if is_final:
                            final_state = state
                            signal = sig
                    
                    # Retrieve the validated trade order from the state
                    validated_order = final_state.get("trade_order")
                    
                    if validated_order:
                        # Use the pre-validated order from the Trade Executor node
                        action = validated_order.get("action", "HOLD").upper()
                        quantity = int(validated_order.get("quantity", 0))
                        reasoning = validated_order.get("reasoning", "No reasoning provided.")
                    else:
                        # Fallback to the SignalProcessor if the graph didn't produce a trade_order
                        action = signal.get("action", "HOLD").upper()
                        intent_amount = float(signal.get("intent_amount", 0))
                        intent_unit = signal.get("intent_unit", "SHARES").upper()
                        reasoning = signal.get("reasoning", "Parsed from text fallback.")
                        
                        if intent_unit == "USD" and current_price > 0:
                            quantity = int(intent_amount // current_price)
                            reasoning = f"(Converted ${intent_amount} -> {quantity} shares) " + reasoning
                        else:
                            quantity = int(intent_amount)
                    
                    # Enhanced Decision Log with reasoning
                    yield {"type": "log", "message": f"🤖 Decision: {action} {quantity} shares"}
                    yield {"type": "log", "message": f"📝 Reasoning: {reasoning}"}
                    
                    # Log Decision
                    yield {
                        "type": "decision", 
                        "data": {
                            "trader": "Agent",
                            "date": current_date,
                            "output": f"{action} {quantity} shares. {reasoning}",
                            "portfolio": {
                                "cash": current_cash,
                                "positions": self.portfolio.positions,
                                "total_equity": current_equity
                            }
                        }
                    }

                    # Execute Trade in Mock Portfolio
                    executed = False
                    if action == "BUY" and quantity > 0:
                        executed = self.portfolio.buy(ticker, current_price, quantity, current_date, reasoning)
                    elif action == "SELL" and quantity > 0:
                        executed = self.portfolio.sell(ticker, current_price, quantity, current_date, reasoning)
                    
                    # Log Trade
                    if executed:
                        journal_entry = {
                            "action": action,
                            "qty": quantity,
                            "price": current_price,
                            "reasoning": reasoning,
                            "time": current_date
                        }
                        journals.append(journal_entry)
                        
                        yield {
                            "type": "trade", 
                            "data": {
                                "trader": "Agent",
                                "action": action,
                                "qty": quantity, 
                                "price": current_price, 
                                "reasoning": reasoning, 
                                "time": current_date
                            }
                        }
                        yield {"type": "log", "message": f"✅ EXECUTED: {action} {quantity} shares @ ${current_price:.2f} = ${quantity * current_price:,.0f}"}
                        
                        # Reflect and update memory with trade outcome
                        # Calculate returns from last trade (if any) to provide feedback
                        if len(journals) >= 2:
                            last_trade = journals[-2]
                            if last_trade["action"] == "BUY":
                                # Calculate return from buy to current price
                                returns = (current_price - last_trade["price"]) / last_trade["price"]
                                returns_losses = f"Return: {returns*100:.2f}%"
                            else:
                                returns_losses = "Neutral (SELL completed)"
                        else:
                            returns_losses = "First trade - no prior return data"
                        
                        try:
                            self.graph.reflect_and_remember(returns_losses)
                            yield {"type": "log", "message": "🧠 Memory updated with trade outcome"}
                        except Exception as mem_error:
                            yield {"type": "log", "message": f"⚠️ Memory update skipped: {str(mem_error)[:50]}"}
                            
                    elif action != "HOLD" and quantity > 0:
                         yield {"type": "log", "message": f"⚠️ Order Failed (Insufficient funds/shares): {action} {quantity}"}
                    elif action == "HOLD":
                         yield {"type": "log", "message": "⏸️ HOLD - No trade executed"}
                    
                    # Update Equity Curve
                    self.portfolio.update_equity({ticker: current_price}, current_date)
                    
                except Exception as e:
                     yield {"type": "log", "message": f"❌ Error running Agent: {e}"}

                # Progress Update
                yield {
                    "type": "progress", 
                    "current": i + 1, 
                    "total": total_candles,
                    "date": current_date, 
                    "equity": self.portfolio.equity_curve[-1]['equity'] if self.portfolio.equity_curve else self.portfolio.cash
                }
                
                # Sleep for UI
                await asyncio.sleep(0.01)

            # --- FINAL RESULTS ---
            final_result = {
                "name": "Trading Agent",
                "initial_cash": 100000.0,
                "final_equity": self.portfolio.equity_curve[-1]['equity'] if self.portfolio.equity_curve else self.portfolio.cash,
                "return_pct": ((self.portfolio.equity_curve[-1]['equity'] - 100000.0) / 100000.0) * 100 if self.portfolio.equity_curve else 0.0,
                "trades": len(journals),
                "history": journals, 
                "equity_curve": self.portfolio.equity_curve
            }
            
            yield {"type": "result", "data": [final_result]}

        except Exception as e:
            yield {"type": "error", "message": str(e)}

if __name__ == "__main__":
    # Test Run
    engine = AgentBacktestEngine()
    # Need to run async loop
    async def run():
         async for event in engine.stream_agent_simulation("NVDA", days=3):
             print(event)
    
    asyncio.run(run())
