"""
RP Trader Adapter for Backtesting
Wraps the original RP Trader logic with mock tools for historical simulation.
"""

import json
import pandas as pd
from datetime import datetime
from typing import Dict, Any, List, Optional
from agents import Agent, Runner, function_tool
from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

from PaperTrader.adapters.mock_tools import (
    MarketDataTool,
    TavilySearchTool,
    SimulatedAccountTool,
    FundamentalsTool,
)

load_dotenv(override=True)


# =============================================================================
# LOCAL COPY OF TRADER INSTRUCTIONS (to avoid importing templates.py which has
# live dependencies on polygon package)
# This is a faithful copy of the original trader_instructions from rp_traders/templates.py
# =============================================================================

def trader_instructions(name: str) -> str:
    """Generate the system prompt for a trader agent."""
    note = "You have access to end of day market data; use your get_price tool to get the share price as of the prior close. You can also use tools for technical indicators and fundamentals."
    return f"""
You are {name}, a trader on the stock market. Your account is under your name, {name}.
You actively manage your portfolio according to your strategy.
You have access to tools including a researcher to research online for news and opportunities, based on your request.
You also have tools to access to financial data for stocks. {note}
And you have tools to buy and sell stocks using your account name {name}.
Use these tools to carry out research, make decisions, and execute trades.
After you've completed trading, reply with a 2-3 sentence appraisal.
Your goal is to maximize your profits according to your strategy.
"""


class RPTraderAdapter:
    """
    Adapter that wraps an RP Trader for backtesting.
    Uses mock tools instead of live MCP servers.
    """

    def __init__(
        self,
        name: str,
        strategy: str,
        df: pd.DataFrame,
        ticker: str,
        model_name: str = "gpt-4o-mini",
        initial_balance: float = 10000.0,
    ):
        """
        Args:
            name: Trader name (Warren, George, Ray, Cathie)
            strategy: The trading strategy description
            df: Pre-downloaded historical price DataFrame
            ticker: Stock ticker being traded
            model_name: LLM model to use
            initial_balance: Starting cash balance
        """
        self.name = name
        self.strategy = strategy
        self.ticker = ticker
        self.model_name = model_name

        # Initialize mock tools
        self.market_data = MarketDataTool(df, ticker)
        self.fundamentals = FundamentalsTool(ticker)
        self.tavily_search = TavilySearchTool()
        self.account = SimulatedAccountTool(name, initial_balance)
        self.account.link_market_data(self.market_data)
        self.fundamentals.link_market_data(self.market_data)

        # Track decisions for analysis
        self.decision_log: List[Dict[str, Any]] = []
        self.current_date: Optional[datetime] = None

        # Build tools for the agent
        self.tools = self._build_tools()

    def _build_tools(self) -> List:
        """Build the function tools that the agent can call."""

        @function_tool
        def get_price() -> str:
            """Get the current stock price and basic OHLCV data."""
            result = self.market_data.get_price()
            return json.dumps(result, indent=2)

        @function_tool
        def get_technical_indicators() -> str:
            """Get technical indicators including RSI, MACD, SMA, EMA, and Bollinger Bands."""
            result = self.market_data.get_technical_indicators()
            return json.dumps(result, indent=2)

        @function_tool
        def get_fundamentals() -> str:
            """Get key fundamental metrics (P/E, Market Cap, EPS, etc.)."""
            result = self.fundamentals.get_key_ratios()
            return json.dumps(result, indent=2)

        @function_tool
        def get_historical_data(days: int = 30) -> str:
            """Get historical OHLCV data for the past N days."""
            result = self.market_data.get_aggregates(days)
            return json.dumps(result, indent=2)

        @function_tool
        def search_news(query: str) -> str:
            """Search for financial news related to the query. Results are filtered to avoid future information."""
            results = self.tavily_search.search(query, max_results=5)
            return json.dumps(results, indent=2)

        @function_tool
        def buy_shares(ticker: str, quantity: int, rationale: str) -> str:
            """Buy shares of a stock. Provide ticker, quantity, and rationale for the trade."""
            result = self.account.buy(ticker, quantity, rationale)
            return json.dumps(result, indent=2)

        @function_tool
        def sell_shares(ticker: str, quantity: int, rationale: str) -> str:
            """Sell shares of a stock. Provide ticker, quantity, and rationale for the trade."""
            result = self.account.sell(ticker, quantity, rationale)
            return json.dumps(result, indent=2)

        @function_tool
        def get_portfolio() -> str:
            """Get current portfolio status including cash, holdings, and P&L."""
            return self.account.get_account_report()

        return [
            get_price,
            get_technical_indicators,
            get_fundamentals,
            get_historical_data,
            search_news,
            buy_shares,
            sell_shares,
            get_portfolio,
        ]

    def _get_model(self):
        """Get the appropriate model configuration."""
        from agents import OpenAIChatCompletionsModel

        if "gpt" in self.model_name:
            return self.model_name  # Use default OpenAI
        elif "gemini" in self.model_name:
            client = AsyncOpenAI(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                api_key=os.getenv("GOOGLE_API_KEY"),
            )
            return OpenAIChatCompletionsModel(model=self.model_name, openai_client=client)
        elif "deepseek" in self.model_name:
            client = AsyncOpenAI(
                base_url="https://api.deepseek.com/v1",
                api_key=os.getenv("DEEPSEEK_API_KEY"),
            )
            return OpenAIChatCompletionsModel(model=self.model_name, openai_client=client)
        else:
            return self.model_name

    async def step(self, current_date: datetime) -> Dict[str, Any]:
        """
        Execute one trading step for the given date.
        
        Args:
            current_date: The simulation date (agent will only see data up to this date)
            
        Returns:
            Dict containing the agent's decision and any trades made
        """
        self.current_date = current_date

        # Update all tools with the current date (anti-lookahead)
        self.market_data.set_current_date(current_date)
        self.tavily_search.set_current_date(current_date)
        self.fundamentals.set_current_date(current_date)

        # Get account state
        account_report = self.account.get_account_report()

        # Build the message using original templates (DO NOT MODIFY trader_instructions)
        # We customize the trade_message slightly to include the simulated date
        message = f"""
Based on your investment strategy, analyze the current market situation and make trading decisions.
Use the available tools to research the stock, check technical indicators, and execute trades as needed.

Your investment strategy:
{self.strategy}

Current account status:
{account_report}

Current simulation date: {current_date.strftime("%Y-%m-%d")}
Ticker being analyzed: {self.ticker}

Now, carry out analysis, make your decision, and execute trades if appropriate.
After you've made your decision, respond with a brief 2-3 sentence appraisal of your portfolio and outlook.
"""

        # Create the agent with the original trader instructions
        agent = Agent(
            name=self.name,
            instructions=trader_instructions(self.name),
            model=self._get_model(),
            tools=self.tools,
        )

        # Run the agent
        try:
            result = await Runner.run(agent, message, max_turns=10)
            output = result.final_output if hasattr(result, 'final_output') else str(result)
        except Exception as e:
            output = f"Error running agent: {str(e)}"

        # Log the decision
        decision_record = {
            "date": str(current_date),
            "name": self.name,
            "output": output,
            "portfolio": self.account.get_portfolio_value(),
            "transactions_today": [
                tx for tx in self.account.transactions
                if tx.get("timestamp", "").startswith(str(current_date.date()))
            ],
        }
        self.decision_log.append(decision_record)

        return decision_record

    def get_summary(self) -> Dict[str, Any]:
        """Get a summary of the trader's performance."""
        portfolio = self.account.get_portfolio_value()
        return {
            "name": self.name,
            "strategy": self.strategy,
            "initial_balance": self.account.initial_balance,
            "final_equity": portfolio["total_equity"],
            "pnl": portfolio["pnl"],
            "pnl_percent": portfolio["pnl_percent"],
            "total_trades": len(self.account.transactions),
            "transactions": self.account.transactions,
            "decision_log": self.decision_log,
        }


# =============================================================================
# PREDEFINED STRATEGIES (from rp_traders convention)
# =============================================================================

STRATEGIES = {
    "Warren": """
You are a value investor in the style of Warren Buffett.
Focus on:
- Companies with strong fundamentals and competitive moats
- Stocks trading below intrinsic value
- Long-term holding periods (buy and hold)
- Quality over quantity - make few but high-conviction trades
- Be patient and wait for the right opportunities
Avoid: Overpaying for growth, speculative bets, frequent trading
    """,
    
    "George": """
You are a trader in the style of George Soros, focused on reflexivity and market psychology.
Focus on:
- Identifying market inefficiencies and mispricings
- Bold, concentrated positions when conviction is high
- Momentum and trend following
- Being willing to change your mind quickly when wrong
- Macro trends and their impact on individual stocks
Avoid: Fighting strong trends, holding losers too long
    """,
    
    "Ray": """
You are a systematic investor in the style of Ray Dalio.
Focus on:
- Risk parity and balanced portfolio construction
- Diversification across uncorrelated assets
- Following pre-defined rules strictly
- Mean reversion and value-based entries
- Regular rebalancing to maintain target allocations
Avoid: Emotional decisions, concentrated positions, fighting the data
    """,
    
    "Cathie": """
You are a growth and innovation investor in the style of Cathie Wood.
Focus on:
- Disruptive technologies and innovation leaders
- High-growth companies even at premium valuations
- Long-term conviction in transformative trends
- Adding to positions on dips (cost averaging)
- Companies benefiting from technological change
Avoid: Value traps, declining industries, overly defensive positions
    """,
}


def create_rp_trader(
    name: str,
    df: pd.DataFrame,
    ticker: str,
    model_name: str = "gpt-4o-mini",
    initial_balance: float = 10000.0,
    custom_strategy: Optional[str] = None,
) -> RPTraderAdapter:
    """
    Factory function to create an RP Trader adapter.
    
    Args:
        name: One of "Warren", "George", "Ray", "Cathie"
        df: Pre-downloaded historical price DataFrame
        ticker: Stock ticker being traded
        model_name: LLM model to use
        initial_balance: Starting cash balance
        custom_strategy: Optional custom strategy (overrides default)
    """
    strategy = custom_strategy or STRATEGIES.get(name, STRATEGIES["Warren"])
    
    return RPTraderAdapter(
        name=name,
        strategy=strategy,
        df=df,
        ticker=ticker,
        model_name=model_name,
        initial_balance=initial_balance,
    )
