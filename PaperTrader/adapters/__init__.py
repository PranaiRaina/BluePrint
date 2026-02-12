# PaperTrader/adapters/__init__.py
"""
Adapters for integrating RP Traders with the Backtester.
"""

from .mock_tools import MarketDataTool, TavilySearchTool, SimulatedAccountTool
from .rp_adapter import RPTraderAdapter, create_rp_trader, STRATEGIES

__all__ = [
    "MarketDataTool",
    "TavilySearchTool",
    "SimulatedAccountTool",
    "RPTraderAdapter",
    "create_rp_trader",
    "STRATEGIES",
]

