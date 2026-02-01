import os
import time
import json
import asyncio
from openai import OpenAI
from pathlib import Path
from dotenv import load_dotenv

# Load Env Vars FIRST
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# --- Integrations ---
from PaperTrader.service import paper_trading_service
# We import existing agents to use as tools
# Assuming these are classes we can instantiate or functions we can call
# Inspecting file shows they are likely classes.
# We will do a lazy import or simple wrapper.


# Configuration
# MODEL_NAME = "gpt-4-turbo" 
MODEL_NAME = "gemini-2.0-flash"

google_key = os.getenv("GOOGLE_API_KEY")
if not google_key:
    raise ValueError(f"GOOGLE_API_KEY not found via {env_path}")

client = OpenAI(
    api_key=google_key,
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)

# --- Tool Definitions ---

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_portfolio",
            "description": "Get the current status of the portfolio, including cash balance and positions.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_price",
            "description": "Get the real-time price of a stock ticker.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string", "description": "The stock ticker symbol (e.g. AAPL)"},
                },
                "required": ["ticker"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "buy_stock",
            "description": "Place a BUY order for a stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "quantity": {"type": "number"},
                    "reason": {"type": "string", "description": "Why you are making this trade."},
                },
                "required": ["ticker", "quantity", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sell_stock",
            "description": "Place a SELL order for a stock.",
            "parameters": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "quantity": {"type": "number"},
                    "reason": {"type": "string", "description": "Why you are making this trade."},
                },
                "required": ["ticker", "quantity", "reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "ask_researcher",
            "description": "Ask the Market Research Agent for information about a company or sector.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The question to ask (e.g. 'What is the sentiment on NVDA?')"},
                },
                "required": ["query"],
            },
        },
    },
]

# --- Tool Executors ---

async def execute_tool(tool_name, args):
    print(f"🛠️ Executing {tool_name} with {args}...")
    
    if tool_name == "get_portfolio":
        # Direct Call to Service (The "Memory")
        # Ensure user exists or use test-user
        user_id = "00000000-0000-0000-0000-000000000000"
        portfolios = paper_trading_service.get_portfolios(user_id)
        if not portfolios:
            paper_trading_service.create_portfolio(user_id, "AI Wolf Portfolio")
            portfolios = paper_trading_service.get_portfolios(user_id)
        return json.dumps(paper_trading_service.get_portfolio_details(user_id, portfolios[0]['id']), default=str)

    elif tool_name == "get_market_price":
        price = paper_trading_service.get_price(args["ticker"])
        return str(price)

    elif tool_name == "buy_stock":
        user_id = "00000000-0000-0000-0000-000000000000"
        p = paper_trading_service.get_portfolios(user_id)[0]
        try:
            res = paper_trading_service.execute_trade(
                user_id, 
                p['id'], 
                args["ticker"], 
                "BUY", 
                args["quantity"], 
                reasoning=args.get("reason", "")
            )
            print(f"✅ BOUGHT {args['ticker']}: {res}")
            return json.dumps(res, default=str)
        except Exception as e:
            return f"Error: {str(e)}"

    elif tool_name == "sell_stock":
        user_id = "00000000-0000-0000-0000-000000000000"
        p = paper_trading_service.get_portfolios(user_id)[0]
        try:
            res = paper_trading_service.execute_trade(
                user_id, 
                p['id'], 
                args["ticker"], 
                "SELL", 
                args["quantity"],
                reasoning=args.get("reason", "")
            )
            print(f"✅ SOLD {args['ticker']}: {res}")
            return json.dumps(res, default=str)
        except Exception as e:
            return f"Error: {str(e)}"

    elif tool_name == "ask_researcher":
        # Lazy import to avoid circular dep issues if any
        try:
            # We assume we can instantiate the agent and call 'analyze' or similar
            # Based on file inspection, we might need to adjust this hook
            from StockAgents.services.researcher_agent import ResearchAgent
            # Mock or Real?
            # Creating a fresh instance might be heavy if it loads models.
            # ideally we'd have a singleton or lightweight interface.
            # For now, let's simulate the output to verify architecture first, 
            # OR lets try to use it if it's lightweight.
            # Checking file content... it seems to call LLM so it's fine.
            agent = ResearchAgent()
            return await agent.analyze(args["query"]) 
        except Exception as e:
            return f"Researcher unavailable: {e}"

    return "Unknown tool"

# --- The Autonomous Loop ---

SYSTEM_PROMPT = """
You are "The Wolf of RoseHacks", an autonomous AI portfolio manager.
Your goal is to generate positive returns ("Alpha") for your client.

You run in a continuous loop. Every time you wake up:
1. Check your Portfolio.
2. If cash is high (> 20%), look for buying opportunities.
3. Use the 'ask_researcher' tool to find high-momentum or undervalued stocks.
4. Execute trades decisively.

Persona: Confident, Analytical, Risk-Aware. 
Log your thoughts clearly before acting.
"""

async def run_cycle(history):
    print("\n--- 🐺 The Wolf Wakes Up ---")
    
    # 1. Add Trigger
    history.append({"role": "user", "content": "Wake up. Check status and trade if needed."})

    # 2. Call LLM
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=history,
        tools=TOOLS,
        tool_choice="auto"
    )
    
    message = response.choices[0].message
    print(f"💭 Wolf's Thought: {message.content or 'Validating...'}")
    
    # 3. Handle Tool Calls
    if message.tool_calls:
        history.append(message) # Add assistant's call to history
        
        for tool_call in message.tool_calls:
            function_name = tool_call.function.name
            arguments = json.loads(tool_call.function.arguments)
            
            result = await execute_tool(function_name, arguments)
            
            history.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "name": function_name,
                "content": str(result)
            })
            
        # 4. Final Response after Tools
        final_res = client.chat.completions.create(
            model=MODEL_NAME,
            messages=history
        )
        print(f"📢 Wolf's Report: {final_res.choices[0].message.content}")
        history.append(final_res.choices[0].message)
    else:
        history.append(message)

    # 5. Prune History (Keep it lightweight)
    if len(history) > 20:
        history = [history[0]] + history[-10:]
    
    return history


async def main():
    print("🚀 Starting Autonomous Agent Loop...")
    
    # Initialize DB Pool
    try:
        from ManagerAgent.db import init_db_pool
        init_db_pool()
        print("✅ Database Connection Pool Initialized")
    except Exception as e:
        print(f"❌ Failed to init DB: {e}")
        return

    history = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    while True:
        try:
            # Check Portfolio Status First
            # We need to know if the agent is active. 
            # Ideally we check the first portfolio since we defaulted to it.
            user_id = "00000000-0000-0000-0000-000000000000"
            portfolios = paper_trading_service.get_portfolios(user_id)
            if portfolios:
                details = paper_trading_service.get_portfolio_details(user_id, portfolios[0]['id'])
                is_active = details['overview'].get('is_active', False)
                
                if not is_active:
                    print(f"zzz Agent Sleeping (Inactive) ...")
                    time.sleep(10)
                    continue
                    
            history = await run_cycle(history)
        except Exception as e:
            print(f"❌ Cycle Error: {e}")
        
        print("Waiting 60s...")
        time.sleep(60)

if __name__ == "__main__":
    asyncio.run(main())
