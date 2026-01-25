"""Test script for CalcAgent - run after adding API keys."""

import asyncio
from CalcAgent.config import GROQ_API_KEY, WOLFRAM_APP_ID

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
    print("Checking API keys...")
    
    if not GROQ_API_KEY or GROQ_API_KEY == "your_groq_api_key_here":
        print("❌ GROQ_API_KEY not set in .env")
        return False
    print(f"✓ GROQ_API_KEY configured (starts with: {GROQ_API_KEY[:10]}...)")
    
    if not WOLFRAM_APP_ID or WOLFRAM_APP_ID == "your_wolfram_app_id_here":
        print("❌ WOLFRAM_APP_ID not set in .env")
        return False
    print(f"✓ WOLFRAM_APP_ID configured: {WOLFRAM_APP_ID}")
    
    return True


async def test_wolfram_api():
    """Test Wolfram Alpha API directly."""
    print("\n" + "=" * 50)
    print("Testing Wolfram Alpha LLM API...")
    print("=" * 50)
    
    from CalcAgent.tools.wolfram import query_wolfram
    
    try:
        result = await query_wolfram("compound interest 1000 dollars at 5% for 10 years")
        print(f"✓ Wolfram API working!")
        print(f"Response preview: {result[:200]}...")
        return True
    except Exception as e:
        print(f"❌ Wolfram API error: {e}")
        return False


async def test_agent(query_name: str, query: str):
    """Test a single query through the agent."""
    from agents import Runner
    from CalcAgent.agent import financial_agent
    
    print(f"\n--- Test: {query_name} ---")
    print(f"Query: {query[:80]}{'...' if len(query) > 80 else ''}")
    
    try:
        result = await Runner.run(financial_agent, query)
        print(f"Response:\n{result.final_output[:500]}{'...' if len(result.final_output) > 500 else ''}")
        return True
    except Exception as e:
        print(f"❌ Error: {e}")
        return False


async def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 60)
    print("CalcAgent Test Suite")
    print("=" * 60)
    
    # Check API keys first
    if not check_api_keys():
        print("\n⚠️  Please add your API keys to .env and try again.")
        return
    
    # Test Wolfram API
    wolfram_ok = await test_wolfram_api()
    if not wolfram_ok:
        print("\n⚠️  Fix Wolfram API before continuing.")
        return
    
    # Test agent with sample queries
    print("\n" + "=" * 50)
    print("Testing Agent with Sample Queries...")
    print("=" * 50)
    
    passed = 0
    for name, query in TEST_QUERIES[:3]:  # Start with first 3 simple queries
        if await test_agent(name, query):
            passed += 1
    
    print("\n" + "=" * 50)
    print(f"Results: {passed}/{len(TEST_QUERIES[:3])} tests passed")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
