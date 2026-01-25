import numpy as np
import pandas as pd
import yfinance as yf
import cvxpy as cp
from StockAgents.backend.core.config import settings
from typing import List, Dict

class PortfolioEngine:
    def __init__(self):
        pass
        
    async def optimize_portfolio(self, assets: List[str], constraints: Dict, current_holdings: Dict[str, float] = None) -> Dict:
        """
        Optimize portfolio allocation using CvXpy (Mean-Variance Optimization).
        Target: Maximize Sharpe Ratio (Maximize Return for given Risk).
        If 'current_holdings' is provided (e.g. {'AAPL': 5000}), calculates Buy/Sell recommendations.
        """
        if not assets:
             return {}
             
        try:
            # 1. Fetch Historical Data (1 Year)
            data = yf.download(assets, period="1y", interval="1d", progress=False)['Close']
            
            # Handle single asset case or potential download errors
            if data.empty or len(assets) < 2:
                # Fallback to even split
                return {
                    "allocation": {asset: 1.0/len(assets) for asset in assets},
                    "expected_return": 0.0,
                    "risk": 0.0,
                    "note": "Not enough data for optimization."
                }
            
            # 2. Calculate Returns and Covariance
            returns = data.pct_change().dropna()
            mean_returns = returns.mean().values
            cov_matrix = returns.cov().values
            
            # 3. Setup Optimization Problem
            num_assets = len(assets)
            weights = cp.Variable(num_assets)
            
            # Objective: Maximize Risk-Adjusted Return (Simplified as Mean - Penalty*Variance)
            # Standard Sharpe maximization is non-convex, so we often minimize variance for target return 
            # OR maximize return - lambda * risk.
            # Here we use: Maximize (Expected Return - Risk_Aversion * Portfolio Variance)
            risk_aversion = 1.0 # Standard
            portfolio_return = mean_returns @ weights
            portfolio_risk = cp.quad_form(weights, cov_matrix)
            
            objective = cp.Maximize(portfolio_return - risk_aversion * portfolio_risk)
            
            # Constraints:
            # 1. Sum of weights = 1 (Fully invested)
            # 2. No short selling (weights >= 0)
            constraints_list = [
                cp.sum(weights) == 1,
                weights >= 0
            ]
            
            # Add custom constraints if passed (e.g. min_weight)
            # if 'min_weight' in constraints: ...
            
            # Solve
            prob = cp.Problem(objective, constraints_list)
            prob.solve()
            
            # 4. Format Results
            optimized_weights = weights.value.round(3)
            
            # Calculate final metrics
            final_return = np.dot(optimized_weights, mean_returns) * 252 # Annualized
            final_risk = np.sqrt(np.dot(optimized_weights.T, np.dot(cov_matrix, optimized_weights))) * np.sqrt(252)
            sharpe = final_return / final_risk if final_risk > 0 else 0
            
            allocation = {asset: float(weight) for asset, weight in zip(assets, optimized_weights)}
            
            # Calculate Rebalancing Plan if holdings provided
            rebalancing_plan = {}
            if current_holdings:
                try:
                    total_value = sum(current_holdings.values())
                    for asset, weight in allocation.items():
                        current_val = current_holdings.get(asset, 0.0)
                        target_val = total_value * weight
                        diff = target_val - current_val
                        
                        rebalancing_plan[asset] = {
                            "current_value": current_val,
                            "target_value": round(target_val, 2),
                            "action": "BUY" if diff > 0 else "SELL",
                            "amount": round(abs(diff), 2)
                        }
                except Exception as e:
                     print(f"Rebalancing Calc Error: {e}")

            return {
                "allocation": allocation,
                "rebalancing_plan": rebalancing_plan,
                "annualized_return": float(round(final_return, 4)),
                "annualized_volatility": float(round(final_risk, 4)),
                "sharpe_ratio": float(round(sharpe, 4)),
                "method": "Markowitz Mean-Variance (cvxpy)"
            }

        except Exception as e:
            print(f"Optimization Error: {e}")
            # Fallback
            return {
                "allocation": {asset: 1.0/len(assets) for asset in assets},
                "error": str(e)
            }

portfolio_engine = PortfolioEngine()
