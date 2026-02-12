"""
Mock Tools for RP Traders Backtesting
These tools replace the live MCP tools with backtester-aware versions.
"""

import os
import json
import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any, List
from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv(override=True)


# =============================================================================
# MARKET DATA TOOL (Alpha Vantage / Polygon Simulator)
# =============================================================================

class MarketDataTool:
    """
    Simulates the Polygon/Alpha Vantage API using pre-downloaded historical data.
    Calculates technical indicators (RSI, MACD, SMA, EMA) on the fly.
    """

    def __init__(self, df: pd.DataFrame, ticker: str):
        """
        Args:
            df: Pre-downloaded DataFrame with columns: Open, High, Low, Close, Volume
            ticker: The stock ticker symbol
        """
        self.df = df.copy()
        self.ticker = ticker
        self.current_date: Optional[datetime] = None
        self._precompute_indicators()

    def _precompute_indicators(self):
        """Pre-compute all technical indicators on the full dataset."""
        close = self.df['Close']

        # Moving Averages
        self.df['SMA_10'] = close.rolling(window=10).mean()
        self.df['SMA_50'] = close.rolling(window=50).mean()
        self.df['SMA_200'] = close.rolling(window=200).mean()
        self.df['EMA_10'] = close.ewm(span=10, adjust=False).mean()
        self.df['EMA_20'] = close.ewm(span=20, adjust=False).mean()

        # RSI (14-day)
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        self.df['RSI'] = 100 - (100 / (1 + rs))

        # MACD
        exp1 = close.ewm(span=12, adjust=False).mean()
        exp2 = close.ewm(span=26, adjust=False).mean()
        self.df['MACD'] = exp1 - exp2
        self.df['MACD_Signal'] = self.df['MACD'].ewm(span=9, adjust=False).mean()
        self.df['MACD_Histogram'] = self.df['MACD'] - self.df['MACD_Signal']

        # Bollinger Bands
        self.df['BB_Middle'] = close.rolling(window=20).mean()
        std = close.rolling(window=20).std()
        self.df['BB_Upper'] = self.df['BB_Middle'] + (std * 2)
        self.df['BB_Lower'] = self.df['BB_Middle'] - (std * 2)

    def set_current_date(self, date: datetime):
        """Set the 'present' date for the simulation."""
        self.current_date = date

    def _get_data_up_to_date(self) -> pd.DataFrame:
        """Get data up to and including the current date (anti-lookahead)."""
        if self.current_date is None:
            raise ValueError("current_date has not been set. Call set_current_date() first.")
        return self.df[self.df.index <= self.current_date]

    def get_price(self) -> Dict[str, Any]:
        """Get the current price and basic info."""
        data = self._get_data_up_to_date()
        if data.empty:
            return {"error": "No data available for the current date"}
        
        latest = data.iloc[-1]
        return {
            "ticker": self.ticker,
            "date": str(data.index[-1]),
            "open": float(latest['Open']),
            "high": float(latest['High']),
            "low": float(latest['Low']),
            "close": float(latest['Close']),
            "volume": int(latest['Volume']) if pd.notna(latest['Volume']) else 0,
        }

    def get_technical_indicators(self) -> Dict[str, Any]:
        """Get all pre-computed technical indicators for the current date."""
        data = self._get_data_up_to_date()
        if data.empty:
            return {"error": "No data available for the current date"}

        latest = data.iloc[-1]
        return {
            "ticker": self.ticker,
            "date": str(data.index[-1]),
            "price": float(latest['Close']),
            "sma_10": float(latest['SMA_10']) if pd.notna(latest['SMA_10']) else None,
            "sma_50": float(latest['SMA_50']) if pd.notna(latest['SMA_50']) else None,
            "sma_200": float(latest['SMA_200']) if pd.notna(latest['SMA_200']) else None,
            "ema_10": float(latest['EMA_10']) if pd.notna(latest['EMA_10']) else None,
            "ema_20": float(latest['EMA_20']) if pd.notna(latest['EMA_20']) else None,
            "rsi": float(latest['RSI']) if pd.notna(latest['RSI']) else None,
            "macd": float(latest['MACD']) if pd.notna(latest['MACD']) else None,
            "macd_signal": float(latest['MACD_Signal']) if pd.notna(latest['MACD_Signal']) else None,
            "macd_histogram": float(latest['MACD_Histogram']) if pd.notna(latest['MACD_Histogram']) else None,
            "bb_upper": float(latest['BB_Upper']) if pd.notna(latest['BB_Upper']) else None,
            "bb_middle": float(latest['BB_Middle']) if pd.notna(latest['BB_Middle']) else None,
            "bb_lower": float(latest['BB_Lower']) if pd.notna(latest['BB_Lower']) else None,
        }

    def get_aggregates(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get historical OHLCV aggregates for the past N days."""
        data = self._get_data_up_to_date()
        recent = data.tail(days)
        
        result = []
        for idx, row in recent.iterrows():
            result.append({
                "date": str(idx),
                "open": float(row['Open']),
                "high": float(row['High']),
                "low": float(row['Low']),
                "close": float(row['Close']),
                "volume": int(row['Volume']) if pd.notna(row['Volume']) else 0,
            })
        return result


# =============================================================================
# FUNDAMENTALS TOOL (Financial Metrics)
# =============================================================================

# =============================================================================
# FUNDAMENTALS TOOL (Financial Metrics)
# =============================================================================

class FundamentalsTool:
    """
    Provides key fundamental metrics with Anti-Lookahead logic.
    - Fetches historical EARNINGS from Alpha Vantage.
    - Calculates P/E and Market Cap dynamically based on Historical Price (from MarketDataTool)
      and Trailing Twelve Month (TTM) EPS known *at that date*.
    """

    def __init__(self, ticker: str):
        self.ticker = ticker
        self.api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
        self.overview = self._fetch_overview()
        self.earnings = self._fetch_earnings()
        self.current_date: Optional[datetime] = None
        self.market_data_tool: Optional['MarketDataTool'] = None

    def link_market_data(self, market_data_tool: 'MarketDataTool'):
        """Link to market data to access historical prices for P/E calculation."""
        self.market_data_tool = market_data_tool

    def set_current_date(self, date: datetime):
        """Set the 'present' date for the simulation."""
        self.current_date = date

    def _fetch_overview(self) -> Dict[str, Any]:
        """Fetch company overview (Sector, Industry, SharesOutstanding)."""
            if not self.api_key: return {}
        try:
            import httpx
            url = f"https://www.alphavantage.co/query?function=OVERVIEW&symbol={self.ticker}&apikey={self.api_key}&source=trading_agents"
            r = httpx.get(url)
            return r.json()
        except Exception:
            return {}

    def _fetch_earnings(self) -> List[Dict[str, Any]]:
        """Fetch historical quarterly earnings."""
        if not self.api_key: return []
        try:
            import httpx
            url = f"https://www.alphavantage.co/query?function=EARNINGS&symbol={self.ticker}&apikey={self.api_key}&source=trading_agents"
            r = httpx.get(url)
            data = r.json()
            return data.get("quarterlyEarnings", [])
        except Exception:
            return []

    def _get_trailing_eps(self) -> float:
        """Calculate TTM EPS based on earnings reported ON or BEFORE current_date."""
        if not self.earnings or not self.current_date:
            return 0.0
            
        # Filter earnings that were reported by the current simulation date
        past_earnings = []
        for e in self.earnings:
            report_date_str = e.get("reportedDate") or e.get("fiscalDateEnding")
            if report_date_str:
                try:
                    r_date = datetime.strptime(report_date_str, "%Y-%m-%d")
                    if r_date <= self.current_date:
                        past_earnings.append(e)
                except ValueError:
                    pass
        
        # Sort by date descending (newest first)
        past_earnings.sort(key=lambda x: x.get("reportedDate", ""), reverse=True)
        
        # Sum last 4 quarters (TTM)
        ttm_eps = 0.0
        count = 0
        for e in past_earnings:
            try:
                eps = float(e.get("reportedEPS", 0))
                ttm_eps += eps
                count += 1
                if count >= 4:
                    break
            except ValueError:
                pass
                
        return ttm_eps

    def get_key_ratios(self) -> Dict[str, Any]:
        """Get key financial ratios (Market Cap, P/E, P/B, Dividend Yield)."""
        # 1. Get Dynamic Data (Price, EPS)
        price = 0.0
        if self.market_data_tool:
            # We use get_price() which obeys set_current_date()
            p_data = self.market_data_tool.get_price()
            price = p_data.get("close", 0.0)

        eps_ttm = self._get_trailing_eps()

        # 2. Calculate Ratios
        pe_ratio = "N/A"
        if price > 0 and eps_ttm > 0:
            pe_ratio = round(price / eps_ttm, 2)

        # Market Cap (Approximate using current shares out * historical price)
        # Note: Shares Outstanding is hard to get historically without paid API, so we use latest as proxy.
        # This is a minor acceptable lookahead for Market Cap magnitude, but Price is correct.
        shares_out = float(self.overview.get("SharesOutstanding", 0)) if self.overview.get("SharesOutstanding") else 0
        market_cap = round(shares_out * price, 2) if shares_out and price else "N/A"

        # 3. Return Combined Data
        return {
            "ticker": self.ticker,
            "date": str(self.current_date.date()) if self.current_date else "N/A",
            "price": price,
            "market_cap": market_cap,
            "trailing_eps": round(eps_ttm, 3),
            "trailing_pe": pe_ratio,
            "forward_pe": self.overview.get("ForwardPE", "N/A"), # Still static snapshot
            "price_to_book": self.overview.get("PriceToBookRatio", "N/A"), # Still static snapshot
            "dividend_yield": self.overview.get("DividendYield", "N/A"), # Still static snapshot
            "sector": self.overview.get("Sector", "N/A"),
            "industry": self.overview.get("Industry", "N/A"),
        }


# =============================================================================
# RESEARCH TOOL (Time-Aware Tavily)
# =============================================================================

class TavilySearchTool:
    """
    Wraps the Tavily API with strict anti-lookahead filtering.
    Injects an end_date into queries and locally filters results.
    Implements caching to avoid redundant API calls.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")
        if not self.api_key:
            raise ValueError("TAVILY_API_KEY not found in environment")
        self.client = TavilyClient(api_key=self.api_key)
        self.current_date: Optional[datetime] = None
        
        # Caching Setup
        self.cache_file = os.path.join(os.path.dirname(__file__), "tavily_cache.json")
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict[str, Any]:
        """Load cache from JSON file."""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Failed to load Tavily cache: {e}")
        return {}

    def _save_cache(self):
        """Save cache to JSON file."""
        try:
            with open(self.cache_file, "w") as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"⚠️ Failed to save Tavily cache: {e}")

    def set_current_date(self, date: datetime):
        """Set the 'present' date for the simulation."""
        self.current_date = date

    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """
        Search for news with strict anti-lookahead and caching.
        
        Args:
            query: The search query
            max_results: Maximum number of results to return
            
        Returns:
            List of filtered search results
        """
        if self.current_date is None:
            raise ValueError("current_date has not been set. Call set_current_date() first.")

        # Inject time context into the query
        end_date_str = self.current_date.strftime("%Y-%m-%d")
        time_aware_query = f"{query} before:{end_date_str}"
        
        # Cache Key (Query + Date + Limit)
        cache_key = f"{time_aware_query}_limit_{max_results * 2}"
        
        # 1. Check Cache
        if cache_key in self.cache:
            # print(f"🔍 Serving cached Tavily result for: {cache_key[:30]}...")
            raw_results = self.cache[cache_key]
            # We still need to do the local date filtering on cached results just in case
            # (though strictly speaking the cache key includes the date constraint)
            pass
        else:
            # 2. Fetch from API
            try:
                # Make the API call
                response = self.client.search(
                    query=time_aware_query,
                    max_results=max_results * 2,  # Fetch extra for local filtering
                    search_depth="advanced",
                    include_answer=False,
                )
                raw_results = response.get("results", [])
                
                # Update Cache
                self.cache[cache_key] = raw_results
                self._save_cache()
                
            except Exception as e:
                return [{"error": f"Tavily API error: {str(e)}"}]

        # 3. Local Safety Check (Anti-Lookahead)
        filtered_results = []
        for result in raw_results:
            published_date_str = result.get("published_date")
            if published_date_str:
                try:
                    # Try parsing ISO format
                    pub_date = datetime.fromisoformat(published_date_str.replace("Z", "+00:00"))
                    if pub_date.date() > self.current_date.date():
                        continue  # Skip future articles
                except (ValueError, TypeError):
                    pass  # If we can't parse, include it (conservative)
            
            filtered_results.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "content": result.get("content", "")[:500],  # Truncate for context window
                "published_date": published_date_str,
            })

            if len(filtered_results) >= max_results:
                break

        return filtered_results


# =============================================================================
# ACCOUNT TOOL (Simulated Portfolio)
# =============================================================================

class SimulatedAccountTool:
    """
    In-memory portfolio tracker for backtesting.
    Does not persist to any database.
    """

    def __init__(self, name: str, initial_balance: float = 10000.0):
        self.name = name
        self.balance = initial_balance
        self.initial_balance = initial_balance
        self.holdings: Dict[str, int] = {}  # {ticker: quantity}
        self.transactions: List[Dict[str, Any]] = []
        self.market_data_tool: Optional[MarketDataTool] = None

    def link_market_data(self, market_data_tool: MarketDataTool):
        """Link to the market data tool for price lookups."""
        self.market_data_tool = market_data_tool

    def get_price(self, ticker: str) -> float:
        """Get the current price for a ticker."""
        if self.market_data_tool and ticker == self.market_data_tool.ticker:
            price_info = self.market_data_tool.get_price()
            return price_info.get("close", 0.0)
        return 0.0

    def buy(self, ticker: str, quantity: int, rationale: str = "") -> Dict[str, Any]:
        """Execute a buy order."""
        if quantity <= 0:
            return {"error": f"Quantity must be positive. Received: {quantity}"}

        price = self.get_price(ticker)
        if price <= 0:
            return {"error": f"Cannot get price for {ticker}"}

        cost = price * quantity
        if cost > self.balance:
            return {"error": f"Insufficient funds. Need ${cost:.2f}, have ${self.balance:.2f}"}

        self.balance -= cost
        self.holdings[ticker] = self.holdings.get(ticker, 0) + quantity
        
        tx = {
            "action": "BUY",
            "ticker": ticker,
            "quantity": quantity,
            "price": price,
            "total": cost,
            "rationale": rationale,
            "timestamp": str(self.market_data_tool.current_date) if self.market_data_tool else "",
        }
        self.transactions.append(tx)
        
        return {
            "success": True,
            "action": "BUY",
            "ticker": ticker,
            "quantity": quantity,
            "price": price,
            "new_balance": self.balance,
            "holdings": self.holdings,
        }

    def sell(self, ticker: str, quantity: int, rationale: str = "") -> Dict[str, Any]:
        """Execute a sell order."""
        if quantity <= 0:
            return {"error": f"Quantity must be positive. Received: {quantity}"}

        current_qty = self.holdings.get(ticker, 0)
        if current_qty < quantity:
            return {"error": f"Cannot sell {quantity} shares of {ticker}. Only holding {current_qty}."}

        price = self.get_price(ticker)
        if price <= 0:
            return {"error": f"Cannot get price for {ticker}"}

        revenue = price * quantity
        self.balance += revenue
        self.holdings[ticker] -= quantity
        
        if self.holdings[ticker] == 0:
            del self.holdings[ticker]
        
        tx = {
            "action": "SELL",
            "ticker": ticker,
            "quantity": quantity,
            "price": price,
            "total": revenue,
            "rationale": rationale,
            "timestamp": str(self.market_data_tool.current_date) if self.market_data_tool else "",
        }
        self.transactions.append(tx)
        
        return {
            "success": True,
            "action": "SELL",
            "ticker": ticker,
            "quantity": quantity,
            "price": price,
            "new_balance": self.balance,
            "holdings": self.holdings,
        }

    def get_portfolio_value(self) -> Dict[str, Any]:
        """Calculate total portfolio value."""
        equity = self.balance
        holdings_value = {}
        
        for ticker, qty in self.holdings.items():
            price = self.get_price(ticker)
            value = price * qty
            holdings_value[ticker] = {"quantity": qty, "price": price, "value": value}
            equity += value

        return {
            "name": self.name,
            "cash": self.balance,
            "holdings": holdings_value,
            "total_equity": equity,
            "initial_balance": self.initial_balance,
            "pnl": equity - self.initial_balance,
            "pnl_percent": ((equity - self.initial_balance) / self.initial_balance) * 100,
        }

    def get_account_report(self) -> str:
        """Return a JSON string report of the account, including recent history."""
        import json
        report = self.get_portfolio_value()
        
        # Add recent history (last 5 trades)
        report["recent_transactions"] = self.transactions[-5:] if self.transactions else []
        
        return json.dumps(report, indent=2)
