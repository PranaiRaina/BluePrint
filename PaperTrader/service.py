
import os
import yfinance as yf
from datetime import datetime
from uuid import uuid4
from fastapi import HTTPException
from ManagerAgent.db import get_db
from StockAgents.services.finnhub_client import finnhub_client

class PaperTradingService:
    def __init__(self):
        pass

    def get_price(self, ticker: str) -> float:
        """
        Get price with fallback strategy:
        1. Finnhub (Real-time, if key works)
        2. Yahoo Finance (Delayed/Scraped, robust fallback)
        """
        # 1. Try Finnhub
        try:
            price = finnhub_client.get_stock_price(ticker)
            if price and price > 0:
                return float(price)
        except Exception as e:
            print(f"Finnhub price fetch failed for {ticker}: {e}")

        # 2. Try YFinance
        try:
            print(f"Falling back to YFinance for {ticker}")
            ticker_obj = yf.Ticker(ticker)
            price = ticker_obj.fast_info.last_price
            if price and price > 0:
                return float(price)
            
            # Ultra fallback (history)
            hist = ticker_obj.history(period="1d")
            if not hist.empty:
                return float(hist['Close'].iloc[-1])
        except Exception as e:
            print(f"YFinance price fetch failed for {ticker}: {e}")
        
        return 0.0
    def create_portfolio(self, user_id: str, name: str):
        with get_db() as conn:
            with conn.cursor() as cursor:
                 pid = str(uuid4())
                 cursor.execute(
                     "INSERT INTO portfolios (id, user_id, name) VALUES (%s, %s, %s) RETURNING *",
                     (pid, user_id, name)
                 )
                 conn.commit()
                 return cursor.fetchone()

    def rename_portfolio(self, user_id: str, portfolio_id: str, new_name: str):
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE portfolios SET name = %s WHERE id = %s AND user_id = %s RETURNING *",
                    (new_name, portfolio_id, user_id)
                )
                conn.commit()
                return cursor.fetchone()

    def delete_portfolio(self, user_id: str, portfolio_id: str):
        with get_db() as conn:
            with conn.cursor() as cursor:
                # Transactions likely cascade due to FK, but let's be safe
                cursor.execute("DELETE FROM transactions WHERE portfolio_id = %s", (portfolio_id,))
                
                cursor.execute(
                    "DELETE FROM portfolios WHERE id = %s AND user_id = %s RETURNING id",
                    (portfolio_id, user_id)
                )
                deleted = cursor.fetchone()
                conn.commit()
                return deleted is not None
    def get_portfolios(self, user_id: str):
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM portfolios WHERE user_id = %s ORDER BY created_at DESC", 
                    (user_id,)
                )
                return cursor.fetchall()
                
    def get_portfolio_details(self, user_id: str, portfolio_id: str):
        with get_db() as conn:
            with conn.cursor() as cursor:
                # 1. Get Portfolio
                cursor.execute(
                    "SELECT * FROM portfolios WHERE id = %s AND user_id = %s",
                    (portfolio_id, user_id)
                )
                portfolio = cursor.fetchone()
                if not portfolio:
                    raise HTTPException(status_code=404, detail="Portfolio not found")
                
                # 2. Get Transactions
                cursor.execute(
                    "SELECT * FROM transactions WHERE portfolio_id = %s ORDER BY executed_at ASC",
                    (portfolio_id,)
                )
                # cursor.execute(...)
                transactions = cursor.fetchall()
                
                # 3. Calculate Positions (Chronological Replay)
                positions = {}
                for tx in transactions:
                    ticker = tx['ticker']
                    qty = float(tx['quantity'])
                    price = float(tx['price_per_share'])
                    tx_type = tx['type']
                    
                    if ticker not in positions:
                        positions[ticker] = {'quantity': 0, 'avg_cost': 0.0, 'total_cost': 0.0}
                    
                    pos = positions[ticker]
                    
                    if tx_type == 'BUY':
                        new_qty = pos['quantity'] + qty
                        new_total_cost = pos['total_cost'] + (qty * price)
                        pos['quantity'] = new_qty
                        pos['total_cost'] = new_total_cost
                        pos['avg_cost'] = new_total_cost / new_qty if new_qty > 0 else 0
                    
                    elif tx_type == 'SELL':
                        new_qty = pos['quantity'] - qty
                        # Reduce total cost proportionally
                        cost_removed = qty * pos['avg_cost']
                        pos['total_cost'] -= cost_removed
                        pos['quantity'] = max(0, new_qty)
                        if pos['quantity'] == 0:
                            pos['total_cost'] = 0.0
                            pos['avg_cost'] = 0.0
                
                # 4. Enrich & Filter
                valid_positions = []
                total_equity = 0.0
                
                for ticker, data in positions.items():
                    if data['quantity'] > 0:
                        price = self.get_price(ticker)
                            
                        market_value = data['quantity'] * price
                        total_equity += market_value
                        
                        valid_positions.append({
                            "ticker": ticker,
                            "quantity": data['quantity'],
                            "avg_cost": data['avg_cost'],
                            "current_price": price,
                            "market_value": market_value,
                            "unrealized_pl": market_value - (data['quantity'] * data['avg_cost']),
                            "unrealized_pl_percent": ((market_value / (data['quantity'] * data['avg_cost'])) - 1) * 100 if data['avg_cost'] > 0 else 0
                        })
                
                return {
                    "overview": {
                        "id": portfolio['id'],
                        "name": portfolio['name'],
                        "cash_balance": float(portfolio['cash_balance']),
                        "total_equity": total_equity,
                        "total_value": float(portfolio['cash_balance']) + total_equity,
                        "day_change": 0.0, 
                        "day_change": 0.0, 
                        "day_change_percent": 0.0,
                        "is_active": bool(portfolio.get('is_active', False))
                    },
                    "positions": valid_positions,
                    "transactions": transactions[-20:][::-1] # Last 20, reversed for display
                }

    def create_portfolio(self, user_id: str, name: str, initial_cash: float = 100000.00):
        with get_db() as conn:
            with conn.cursor() as cursor:
                portfolio_id = str(uuid4())
                cursor.execute(
                    "INSERT INTO portfolios (id, user_id, name, cash_balance) VALUES (%s, %s, %s, %s) RETURNING *",
                    (portfolio_id, user_id, name, initial_cash)
                )
                return cursor.fetchone()

    def execute_trade(self, user_id: str, portfolio_id: str, ticker: str, action: str, quantity: float):
        if quantity <= 0:
            raise HTTPException(status_code=400, detail="Quantity must be positive")
            
        action = action.upper()
        if action not in ['BUY', 'SELL']:
            raise HTTPException(status_code=400, detail="Invalid action")

        with get_db() as conn:
            with conn.cursor() as cursor:
                # 1. Validate Portfolio Ownership
                cursor.execute("SELECT * FROM portfolios WHERE id = %s AND user_id = %s FOR UPDATE", (portfolio_id, user_id))
                portfolio = cursor.fetchone()
                if not portfolio:
                    raise HTTPException(status_code=404, detail="Portfolio not found")
                
                current_price = self.get_price(ticker)
                if not current_price or current_price <= 0:
                    raise HTTPException(status_code=400, detail=f"Could not fetch valid price for {ticker}")
                
                cost = current_price * quantity

                if action == "BUY":
                    if float(portfolio['cash_balance']) < cost:
                        raise HTTPException(status_code=400, detail="Insufficient funds")
                    new_balance = float(portfolio['cash_balance']) - cost
                elif action == "SELL":
                    # Check holdings
                    cursor.execute("""
                        SELECT SUM(CASE WHEN type = 'BUY' THEN quantity ELSE -quantity END) as net_qty
                        FROM transactions WHERE portfolio_id = %s AND ticker = %s
                    """, (portfolio_id, ticker))
                    result = cursor.fetchone()
                    holdings = result['net_qty'] if result and result['net_qty'] else 0
                    if holdings < quantity:
                         raise HTTPException(status_code=400, detail="Insufficient holdings")
                    new_balance = float(portfolio['cash_balance']) + cost
                else:
                    raise HTTPException(status_code=400, detail="Invalid action")

                # 2. Record Transaction
                cursor.execute("""
                    INSERT INTO transactions (id, portfolio_id, ticker, type, quantity, price_per_share, executed_at, reasoning)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s)
                    RETURNING *
                """, (str(uuid4()), portfolio_id, ticker, action, quantity, current_price, reasoning))
                transaction = cursor.fetchone()

                # 3. Update Cash
                cursor.execute("UPDATE portfolios SET cash_balance = %s, updated_at = NOW() WHERE id = %s", (new_balance, portfolio_id))
                
                conn.commit()
                return dict(transaction)

    def _get_holding_qty(self, cursor, portfolio_id, ticker):
        """Helper to get current qty of a ticker from transactions"""
        cursor.execute(
            """
            SELECT type, quantity FROM transactions 
            WHERE portfolio_id = %s AND ticker = %s
            """,
            (portfolio_id, ticker)
        )
        txs = cursor.fetchall()
        net_qty = 0.0
        for row in txs:
            # Row is dictionary-like in psycopg 3 RowFactory? No, it's tuple if not configured...
            # Wait, get_db configures RowFactory? Actually db.py says RealDictCursor usually? 
            # Psycopg 3 uses row_factory=dict_row usually.
            # Let's assume dict access based on previous code.
            qty = float(row['quantity'])
            if row['type'] == 'BUY':
                net_qty += qty
            else:
                net_qty -= qty
        return net_qty

    def toggle_agent(self, user_id: str, portfolio_id: str, is_active: bool) -> dict:
        """Toggle the autonomous agent on/off for a portfolio"""
        with get_db() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE portfolios SET is_active = %s, updated_at = NOW() WHERE id = %s AND user_id = %s RETURNING *",
                    (is_active, portfolio_id, user_id)
                )
                portfolio = cursor.fetchone()
                if not portfolio:
                    raise HTTPException(status_code=404, detail="Portfolio not found")
                conn.commit()
                return dict(portfolio)

paper_trading_service = PaperTradingService()
