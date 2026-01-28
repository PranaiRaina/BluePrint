import httpx
from StockAgents.backend.core.config import settings
from typing import List, Dict

class FinnhubClient:
    def __init__(self):
        self.api_key = settings.FINNHUB_API_KEY
        self.base_url = "https://finnhub.io/api/v1"

    async def get_quote(self, symbol: str) -> Dict:
        """Get real-time quote data for a symbol."""
        if not self.api_key:
            return {"error": "No Finnhub API Key"}
            
        params = {"symbol": symbol, "token": self.api_key}
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.base_url}/quote", params=params)
            if resp.status_code == 200:
                return resp.json()
            return {}

    async def filter_market_movers(self, symbols: List[str], min_change_percent: float = 0) -> List[Dict]:
        """
        Filter a list of symbols to find those exceeding a certain % change.
        Useful for 'Show me gainers in my portfolio'.
        """
        results = []
        for sym in symbols:
            quote = await self.get_quote(sym)
            # Finnhub Quote: c=Current, d=Change, dp=Percent Change, h=High, l=Low, o=Open, pc=Previous Close
            if quote and 'dp' in quote:
                if quote['dp'] >= min_change_percent:
                    results.append({
                        "symbol": sym,
                        "price": quote['c'],
                        "change_percent": quote['dp']
                    })
        return sorted(results, key=lambda x: x['change_percent'], reverse=True)

    async def get_candles(self, symbol: str, resolution: str = "D", time_range: str = "3m") -> Dict:
        """
        Fetches REAL candle data using yfinance (acting as a fallback for Finnhub free tier).
        ranges: 1d, 1w, 1m, 3m, 6m, 1y
        """
        import yfinance as yf
        import pandas as pd
        from datetime import datetime, timedelta

        try:
            stock = yf.Ticker(symbol)
            
            # Map range to yfinance period/interval
            period = "3mo"
            interval = "1d"
            
            if time_range == "1d":
                period = "1d"
                interval = "5m"
            elif time_range == "1w":
                period = "5d"
                interval = "15m"
            elif time_range == "1m":
                period = "1mo"
                interval = "1d"
            elif time_range == "6m":
                period = "6mo"
                interval = "1d"
            elif time_range == "1y":
                period = "1y"
                interval = "1d"
            # Default 3m (already set)
                
            hist = stock.history(period=period, interval=interval)
            
            if hist.empty:
                return {"s": "no_data"}

            # Convert to Finnhub format
            # c: Close, o: Open, h: High, l: Low, t: Timestamp
            
            c = hist['Close'].tolist()
            o = hist['Open'].tolist()
            h = hist['High'].tolist()
            l = hist['Low'].tolist()
            # Convert pandas timestamps to unix integers
            t = [int(ts.timestamp()) for ts in hist.index]
            dates = [ts.strftime('%Y-%m-%d') for ts in hist.index]
            
            return {
                "c": c,
                "o": o,
                "h": h,
                "l": l,
                "t": t,
                "dates": dates,
                "s": "ok"
            }
        except Exception as e:
            print(f"Error fetching real candles for {symbol}: {e}")
            return {"s": "error", "error": str(e)}

    async def get_company_metrics(self, symbol: str) -> Dict:
        """
        Fetches company basic financials from Finnhub.
        Returns: {beta, 52WeekHigh, 52WeekLow, peRatio}
        """
        if not self.api_key:
            return {"error": "No Finnhub API Key"}
        
        params = {"symbol": symbol.upper(), "metric": "all", "token": self.api_key}
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{self.base_url}/stock/metric", params=params)
                if resp.status_code == 200:
                    data = resp.json()
                    metric_data = data.get('metric', {})
                    return {
                        "ticker": symbol.upper(),
                        "beta": metric_data.get("beta"),
                        "52WeekHigh": metric_data.get("52WeekHigh"),
                        "52WeekLow": metric_data.get("52WeekLow"),
                        "peRatio": metric_data.get("peTTM"),
                        "source": "finnhub"
                    }
            except Exception as e:
                return {"error": f"Finnhub metrics error: {str(e)}"}
        return {}

    async def get_analyst_ratings(self, symbol: str) -> Dict:
        """
        Fetches Wall Street analyst recommendations from Finnhub.
        Returns: {buy, sell, hold, strongBuy, strongSell, consensusScore, recommendation}
        """
        if not self.api_key:
            return {"error": "No Finnhub API Key"}
        
        params = {"symbol": symbol.upper(), "token": self.api_key}
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(f"{self.base_url}/stock/recommendation", params=params)
                if resp.status_code == 200:
                    recs = resp.json()
                    
                    if not recs or len(recs) == 0:
                        return {"error": "No analyst ratings found", "ticker": symbol.upper()}
                    
                    # Get latest month's data
                    latest = recs[0]
                    
                    strong_buy = latest.get("strongBuy", 0)
                    buy = latest.get("buy", 0)
                    hold = latest.get("hold", 0)
                    sell = latest.get("sell", 0)
                    strong_sell = latest.get("strongSell", 0)
                    
                    total = strong_buy + buy + hold + sell + strong_sell
                    
                    if total == 0:
                        return {"error": "No analyst ratings available", "ticker": symbol.upper()}
                    
                    # Calculate weighted consensus (-2 to +2 scale)
                    weighted = (strong_buy * 2 + buy * 1 + hold * 0 + sell * -1 + strong_sell * -2) / total
                    
                    # Normalize to 0-100 scale
                    consensus_score = int((weighted + 2) * 25)
                    
                    # Determine recommendation
                    if consensus_score >= 70:
                        recommendation = "STRONG BUY"
                    elif consensus_score >= 55:
                        recommendation = "BUY"
                    elif consensus_score >= 45:
                        recommendation = "HOLD"
                    elif consensus_score >= 30:
                        recommendation = "SELL"
                    else:
                        recommendation = "STRONG SELL"
                    
                    return {
                        "ticker": symbol.upper(),
                        "strongBuy": strong_buy,
                        "buy": buy,
                        "hold": hold,
                        "sell": sell,
                        "strongSell": strong_sell,
                        "totalAnalysts": total,
                        "consensusScore": consensus_score,
                        "recommendation": recommendation,
                        "period": latest.get("period"),
                        "source": "finnhub_analysts"
                    }
            except Exception as e:
                return {"error": f"Finnhub analyst ratings error: {str(e)}"}
        return {}

finnhub_client = FinnhubClient()
