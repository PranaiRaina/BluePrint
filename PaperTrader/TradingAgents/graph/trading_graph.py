# TradingAgents/graph/trading_graph.py

import os
from pathlib import Path
import json
from typing import Dict, Any

from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI

from langgraph.prebuilt import ToolNode

from TradingAgents.agents import *
from TradingAgents.default_config import DEFAULT_CONFIG
from TradingAgents.agents.utils.memory import FinancialSituationMemory
from TradingAgents.dataflows.config import set_config

# Import the new abstract tool methods from agent_utils
# Import the new abstract tool methods from correct files
from TradingAgents.agents.utils.core_stock_tools import get_stock_data
from TradingAgents.agents.utils.technical_indicators_tools import get_indicators
from TradingAgents.agents.utils.fundamental_data_tools import (
    get_fundamentals,
    get_balance_sheet,
    get_cashflow,
    get_income_statement,
)
from TradingAgents.agents.utils.news_data_tools import (
    get_news,
    get_insider_sentiment,
    get_insider_transactions,
    get_global_news,
    get_social_news,
)

from .conditional_logic import ConditionalLogic
from .setup import GraphSetup
from .propagation import Propagator
from .reflection import Reflector
from .signal_processing import SignalProcessor


class TradingAgentsGraph:
    """Main class that orchestrates the trading agents framework."""

    def __init__(
        self,
        selected_analysts=["market", "social", "news", "fundamentals"],
        debug=False,
        config: Dict[str, Any] = None,
    ):
        """Initialize the trading agents graph and components.

        Args:
            selected_analysts: List of analyst types to include
            debug: Whether to run in debug mode
            config: Configuration dictionary. If None, uses default config
        """
        self.debug = debug
        self.config = config or DEFAULT_CONFIG

        # Update the interface's config
        set_config(self.config)

        # Create necessary directories
        os.makedirs(
            os.path.join(self.config["project_dir"], "dataflows/data_cache"),
            exist_ok=True,
        )

        # Initialize LLMs
        if self.config["llm_provider"].lower() in ["gemini", "google"]:
            api_key = os.getenv("GOOGLE_API_KEY")
            
            # Using native Google provider to allow disabling safety filters
            safety_settings = {
                "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
                "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
                "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
                "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
            }
            
            self.deep_thinking_llm = ChatGoogleGenerativeAI(
                model=self.config["deep_think_llm"],
                google_api_key=api_key,
                safety_settings=safety_settings
            )
            self.quick_thinking_llm = ChatGoogleGenerativeAI(
                model=self.config["quick_think_llm"],
                google_api_key=api_key,
                safety_settings=safety_settings
            )
        elif self.config["llm_provider"].lower() in ["openai", "ollama", "openrouter"]:
            api_key = os.getenv("OPENAI_API_KEY")
            
            self.deep_thinking_llm = ChatOpenAI(
                model=self.config["deep_think_llm"], 
                base_url=self.config["backend_url"],
                api_key=api_key
            )
            self.quick_thinking_llm = ChatOpenAI(
                model=self.config["quick_think_llm"], 
                base_url=self.config["backend_url"],
                api_key=api_key
            )
        elif self.config["llm_provider"].lower() == "anthropic":
            self.deep_thinking_llm = ChatAnthropic(model=self.config["deep_think_llm"], base_url=self.config["backend_url"])
            self.quick_thinking_llm = ChatAnthropic(model=self.config["quick_think_llm"], base_url=self.config["backend_url"])
        else:
            raise ValueError(f"Unsupported LLM provider: {self.config['llm_provider']}")
        
        # Initialize memories
        self.bull_memory = FinancialSituationMemory("bull_memory", self.config)
        self.bear_memory = FinancialSituationMemory("bear_memory", self.config)
        self.trader_memory = FinancialSituationMemory("trader_memory", self.config)
        self.invest_judge_memory = FinancialSituationMemory("invest_judge_memory", self.config)
        self.risk_manager_memory = FinancialSituationMemory("risk_manager_memory", self.config)

        # Create tool nodes
        self.tool_nodes = self._create_tool_nodes()

        # Initialize components
        self.conditional_logic = ConditionalLogic()
        self.graph_setup = GraphSetup(
            self.quick_thinking_llm,
            self.deep_thinking_llm,
            self.tool_nodes,
            self.bull_memory,
            self.bear_memory,
            self.trader_memory,
            self.invest_judge_memory,
            self.risk_manager_memory,
            self.conditional_logic,
        )

        self.propagator = Propagator()
        self.reflector = Reflector(self.quick_thinking_llm)
        self.signal_processor = SignalProcessor(self.quick_thinking_llm)

        # State tracking
        self.curr_state = None
        self.ticker = None
        self.log_states_dict = {}  # date to full state dict

        # Set up the graph
        self.graph = self.graph_setup.setup_graph(selected_analysts)

    def _create_tool_nodes(self) -> Dict[str, ToolNode]:
        """Create tool nodes for different data sources using abstract methods."""
        return {
            "market": ToolNode(
                [
                    # Core stock data tools
                    get_stock_data,
                    # Technical indicators
                    get_indicators,
                ]
            ),
            "social": ToolNode(
                [
                    # News tools for social media analysis
                    get_social_news,
                ]
            ),
            "news": ToolNode(
                [
                    # News and insider information
                    get_news,
                    get_global_news,
                    get_insider_sentiment,
                    get_insider_transactions,
                ]
            ),
            "fundamentals": ToolNode(
                [
                    # Fundamental analysis tools
                    get_fundamentals,
                    get_balance_sheet,
                    get_cashflow,
                    get_income_statement,
                ]
            ),
        }

    def propagate(
        self,
        company_name: str,
        trade_date: str,
        portfolio_cash: float = 0.0,
        current_shares: int = 0,
        portfolio_value: float = 0.0,
        current_price: float = 100.0,
    ):
        """Run the trading agents graph for a company on a specific date."""

        self.ticker = company_name

        # Initialize state
        init_agent_state = self.propagator.create_initial_state(
            company_name,
            trade_date,
            portfolio_cash=portfolio_cash,
            current_shares=current_shares,
            portfolio_value=portfolio_value,
            current_price=current_price,
        )
        args = self.propagator.get_graph_args()

        if self.debug:
            # Debug mode with tracing
            trace = []
            for chunk in self.graph.stream(init_agent_state, **args):
                if len(chunk["messages"]) == 0:
                    pass
                else:
                    chunk["messages"][-1].pretty_print()
                    trace.append(chunk)

            final_state = trace[-1]
        else:
            # Standard mode without tracing
            final_state = self.graph.invoke(init_agent_state, **args)

        # Store current state for reflection
        self.curr_state = final_state

        # Log state
        self._log_state(trade_date, final_state)

        # Return decision and processed signal
        return final_state, self.process_signal(final_state["final_trade_decision"])

    def propagate_with_steps(
        self,
        company_name: str,
        trade_date: str,
        portfolio_cash: float = 0.0,
        current_shares: int = 0,
        portfolio_value: float = 0.0,
        current_price: float = 100.0,
    ):
        """
        Run the trading agents graph with step-by-step progress updates.
        Yields: (step_name, is_final, final_state_or_none, signal_or_none)
        """
        self.ticker = company_name

        # Initialize state
        init_agent_state = self.propagator.create_initial_state(
            company_name,
            trade_date,
            portfolio_cash=portfolio_cash,
            current_shares=current_shares,
            portfolio_value=portfolio_value,
            current_price=current_price,
        )
        args = self.propagator.get_graph_args()

        # Yield progress indicator
        yield ("🔄 Running AI Analysis Pipeline...", False, None, None)
        
        # Run the full graph with streaming to capture steps
        
        # Override to use stream_mode="updates" so we get node names for logging
        stream_args = args.copy()
        stream_args["stream_mode"] = "updates"
        
        curr_state = init_agent_state.copy()
        
        try:
            for chunk in self.graph.stream(init_agent_state, **stream_args):
                for node_name, update in chunk.items():
                    # Yield execution log for this node
                    yield (f"✅ Executed: {node_name}", False, None, None)
                    
                    # Merge update into curr_state
                    # Note: This is a shallow merge. For deeply nested dicts like debate_state, 
                    # we rely on the specific node returning the full nested object or LangGraph's reducer.
                    # Since we are just logging the final state, assuming 'update' contains the 
                    # specific modified keys is sufficient for tracking.
                    curr_state.update(update)
            
            full_state = curr_state
            self.curr_state = full_state
            self._log_state(trade_date, full_state)
            signal = self.process_signal(full_state["final_trade_decision"])
            yield ("✅ Analysis Complete", True, full_state, signal)
            
        except Exception as e:
            print(f"Graph Execution Error: {e}")
            import traceback
            traceback.print_exc()
            yield (f"❌ Error: {e}", True, None, None)
            return


    def _log_state(self, trade_date, final_state):
        """Log the final state to a JSON file."""
        self.log_states_dict[str(trade_date)] = {
            "company_of_interest": final_state["company_of_interest"],
            "trade_date": final_state["trade_date"],
            "market_report": final_state["market_report"],
            "sentiment_report": final_state["sentiment_report"],
            "news_report": final_state["news_report"],
            "fundamentals_report": final_state["fundamentals_report"],
            "investment_debate_state": {
                "bull_history": final_state["investment_debate_state"]["bull_history"],
                "bear_history": final_state["investment_debate_state"]["bear_history"],
                "history": final_state["investment_debate_state"]["history"],
                "current_response": final_state["investment_debate_state"][
                    "current_response"
                ],
                "judge_decision": final_state["investment_debate_state"][
                    "judge_decision"
                ],
            },
            "trader_investment_decision": final_state["trader_investment_plan"],
            "risk_debate_state": {
                "risky_history": final_state["risk_debate_state"]["risky_history"],
                "safe_history": final_state["risk_debate_state"]["safe_history"],
                "neutral_history": final_state["risk_debate_state"]["neutral_history"],
                "history": final_state["risk_debate_state"]["history"],
                "judge_decision": final_state["risk_debate_state"]["judge_decision"],
            },
            "investment_plan": final_state["investment_plan"],
            "final_trade_decision": final_state["final_trade_decision"],
        }

        # Save to file
        directory = Path(f"eval_results/{self.ticker}/TradingAgentsStrategy_logs/")
        directory.mkdir(parents=True, exist_ok=True)

        with open(
            f"eval_results/{self.ticker}/TradingAgentsStrategy_logs/full_states_log_{trade_date}.json",
            "w",
        ) as f:
            json.dump(self.log_states_dict, f, indent=4)

    def reflect_and_remember(self, returns_losses):
        """Reflect on decisions and update memory based on returns."""
        self.reflector.reflect_bull_researcher(
            self.curr_state, returns_losses, self.bull_memory
        )
        self.reflector.reflect_bear_researcher(
            self.curr_state, returns_losses, self.bear_memory
        )
        self.reflector.reflect_trader(
            self.curr_state, returns_losses, self.trader_memory
        )
        self.reflector.reflect_invest_judge(
            self.curr_state, returns_losses, self.invest_judge_memory
        )
        self.reflector.reflect_risk_manager(
            self.curr_state, returns_losses, self.risk_manager_memory
        )

    def process_signal(self, full_signal):
        """Process a signal to extract the core decision."""
        return self.signal_processor.process_signal(full_signal)
