"""
Wolfram Tool - Math Engine for Risk Analysis

Architecture:
1. yfinance provides historical price data (secondary data source)
2. Wolfram does the mathematical computation (volatility, log returns)
3. Finnhub provides real-time quotes and metrics (primary data source)

This separates data sources from compute engine.
"""
import re
import math
import os
from dotenv import load_dotenv

load_dotenv()

# Config
WOLFRAM_KEY_ID = os.getenv("WOLFRAM_KEY_ID")
WOLFRAM_KEY_SECRET = os.getenv("WOLFRAM_KEY_SECRET")

# Try importing Wolfram client
try:
    from wolframclient.evaluation import WolframCloudSession, SecuredAuthenticationKey
    from wolframclient.language import wlexpr
    WOLFRAM_AVAILABLE = True
except ImportError:
    WOLFRAM_AVAILABLE = False

def wolfram_compute_volatility(prices: list) -> dict:
    """
    Uses Wolfram Cloud to compute volatility from price data.
    
    Input: List of closing prices from Finnhub
    Output: {volatility, annualized_volatility, trend}
    
    This is a BLOCKING call - must be run in executor.
    """
    if not prices or len(prices) < 10:
        return {"error": "Insufficient price data (need at least 10 data points)"}
    
    if not WOLFRAM_AVAILABLE or not WOLFRAM_KEY_ID or not WOLFRAM_KEY_SECRET:
        # Log warning about fallback
        print("[WARN] Wolfram Cloud not configured. Using Python fallback for volatility calculation.")
        result = python_compute_volatility(prices)
        result["warning"] = "Wolfram Cloud not configured. Using Python fallback."
        return result
    
    session = None
    try:
        # Connect to Wolfram Cloud
        sak = SecuredAuthenticationKey(WOLFRAM_KEY_ID, WOLFRAM_KEY_SECRET)
        session = WolframCloudSession(credentials=sak)
        session.start()
        
        # Convert prices to Wolfram list format
        prices_str = "{" + ",".join(str(p) for p in prices) + "}"
        
        # Wolfram code to compute volatility from provided prices
        wolfram_code = f"""
        Module[{{prices = {prices_str}, returns, dailyVol, annualVol, trend}},
            (* Calculate log returns *)
            returns = Differences[Log[prices]];
            
            (* Daily volatility (standard deviation of returns) *)
            dailyVol = StandardDeviation[returns];
            
            (* Annualized volatility (multiply by sqrt of trading days) *)
            annualVol = dailyVol * Sqrt[252];
            
            (* Trend: UP if last price > first price *)
            trend = If[Last[prices] > First[prices], "UP", "DOWN"];
            
            <|
                "dailyVolatility" -> dailyVol,
                "annualizedVolatility" -> annualVol,
                "trend" -> trend,
                "dataPoints" -> Length[prices],
                "source" -> "wolfram_cloud"
            |>
        ]
        """
        
        result = session.evaluate(wlexpr(wolfram_code))
        
        # Safely convert result
        if hasattr(result, 'keys'):
            return dict(result)
        elif isinstance(result, dict):
            return result
        else:
            return {"raw_result": str(result), "source": "wolfram_cloud"}
            
    except Exception as e:
        # Fallback to Python on error
        print(f"Wolfram error, falling back to Python: {e}")
        return python_compute_volatility(prices)
        
    finally:
        if session:
            try:
                session.terminate()
            except:
                pass

def python_compute_volatility(prices: list) -> dict:
    """
    Pure Python fallback for volatility calculation.
    Used when Wolfram is not available.
    """
    if len(prices) < 2:
        return {"error": "Insufficient data"}
    
    # Calculate log returns
    returns = []
    for i in range(1, len(prices)):
        if prices[i-1] > 0 and prices[i] > 0:
            returns.append(math.log(prices[i] / prices[i-1]))
    
    if not returns:
        return {"error": "Could not calculate returns"}
    
    # Calculate standard deviation
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    daily_vol = math.sqrt(variance)
    annual_vol = daily_vol * math.sqrt(252)
    
    trend = "UP" if prices[-1] > prices[0] else "DOWN"
    
    return {
        "dailyVolatility": round(daily_vol, 6),
        "annualizedVolatility": round(annual_vol, 4),
        "trend": trend,
        "dataPoints": len(prices),
        "source": "python_fallback"
    }

def wolfram_risk_analysis(ticker: str, prices: list = None, metrics: dict = None, analyst_ratings: dict = None) -> dict:
    """
    Full risk analysis pipeline using Wolfram.
    
    Args:
        ticker: Stock ticker symbol
        prices: Optional list of closing prices (if not provided, fetches from yfinance)
        metrics: Optional company metrics dict
        analyst_ratings: Optional analyst ratings dict
    
    Returns:
        Combined risk analysis dict
    """
    from StockAgents.tools.yfinance_tool import get_historical_prices
    
    ticker = ticker.upper().strip()
    
    if not re.match(r'^[A-Z]{1,5}$', ticker):
        return {"error": "Invalid ticker format"}
    
    # Step 1: Get historical prices if not provided
    if not prices:
        history = get_historical_prices(ticker, days=90)
        prices = history.get("prices", []) if "error" not in history else []
    
    # Step 2: Compute volatility if prices are available
    volatility_result = {}
    if prices and len(prices) >= 10:
        volatility_result = wolfram_compute_volatility(prices)
    else:
        volatility_result = {"error": "Insufficient price data for volatility calculation"}
    
    # Step 3: Combine results
    result = {
        "ticker": ticker,
        "dataPoints": len(prices),
    }
    
    # Add volatility data
    if "error" not in volatility_result:
        result["annualizedVolatility"] = volatility_result.get("annualizedVolatility")
        result["dailyVolatility"] = volatility_result.get("dailyVolatility")
        result["trend"] = volatility_result.get("trend")
        result["source"] = volatility_result.get("source", "wolfram_cloud")
    else:
        result["volatilityError"] = volatility_result.get("error")
        result["source"] = "error"
    
    # Add company metrics if provided
    if metrics:
        result["beta"] = metrics.get("beta")
        result["peRatio"] = metrics.get("peRatio")
        result["dividendYield"] = metrics.get("dividendYield")
        result["52WeekHigh"] = metrics.get("52WeekHigh")
        result["52WeekLow"] = metrics.get("52WeekLow")
    
    # Add analyst ratings if provided
    if analyst_ratings and "error" not in analyst_ratings:
        result["analystConsensusScore"] = analyst_ratings.get("consensusScore")
        result["analystRecommendation"] = analyst_ratings.get("recommendation")
        result["totalAnalysts"] = analyst_ratings.get("totalAnalysts")
        result["buyCount"] = analyst_ratings.get("buy", 0) + analyst_ratings.get("strongBuy", 0)
        result["sellCount"] = analyst_ratings.get("sell", 0) + analyst_ratings.get("strongSell", 0)
        result["holdCount"] = analyst_ratings.get("hold", 0)
    
    return result
