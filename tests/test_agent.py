"""Test script for CalcAgent - run after adding API keys."""

import pytest
import asyncio
from CalcAgent.config import GOOGLE_API_KEY, WOLFRAM_APP_ID

# Test queries from the implementation plan
TEST_QUERIES = [
    # Simple queries (baseline)
    ("TVM", "What will $10,000 be worth in 20 years at 7% annual interest?"),
    ("Loan", "I have a $200,000 mortgage at 6.5% for 30 years. What's my monthly payment?"),
    ("Tax", "What would my federal taxes be on $85,000 income filing single?"),
    
    # Complex query with noise
    ("TVM with fluff", "So I've been thinking about retirement lately. If I put $50,000 into an index fund today at 8% average returns, what would that be worth when I'm 65 in 30 years?"),
    
    # Insufficient info (should ask clarifying questions)
    ("Missing info", "How much will my money grow?"),
]

def check_api_keys():
    """Verify API keys are configured."""
    if not GOOGLE_API_KEY or GOOGLE_API_KEY == "your_google_api_key_here":
        return False
    if not WOLFRAM_APP_ID or WOLFRAM_APP_ID == "your_wolfram_app_id_here":
        return False
    return True

@pytest.mark.skipif(not check_api_keys(), reason="API keys not configured")
@pytest.mark.asyncio
async def test_wolfram_api():
    """Test Wolfram Alpha API directly."""
    from CalcAgent.tools.wolfram import query_wolfram
    
    try:
        result = await query_wolfram("compound interest 1000 dollars at 5% for 10 years")
        assert result is not None
        assert len(str(result)) > 0
        print(f"Wolfram Response: {str(result)[:100]}...")
    except Exception as e:
        pytest.fail(f"Wolfram API error: {e}")

@pytest.mark.skipif(not check_api_keys(), reason="API keys not configured")
@pytest.mark.asyncio
@pytest.mark.parametrize("name, query", TEST_QUERIES)
async def test_agent(name: str, query: str):
    """Test a single query through the agent."""
    from agents import Runner
    from CalcAgent.src.agent import financial_agent
    
    print(f"\n--- Test: {name} ---")
    
    try:
        # We need to run this in a way that doesn't conflict with existing event loops if any
        result = await Runner.run(financial_agent, query)
        assert result.final_output is not None
        assert len(result.final_output) > 0
        print(f"Response: {result.final_output[:200]}...")
    except Exception as e:
        pytest.fail(f"Agent execution error: {e}")
