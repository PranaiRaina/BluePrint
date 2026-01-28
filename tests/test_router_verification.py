
import pytest
from ManagerAgent.router_intelligence import classify_intent, IntentType

# Test cases for router verification
TEST_CASES = [
    # STOCK
    ("What is the price of NVDA?", IntentType.STOCK),
    ("Show me Apple's dividend history", IntentType.STOCK),
    
    # RAG
    ("What does the uploaded report say about revenue?", IntentType.RAG),
    ("Summarize the PDF I sent you", IntentType.RAG),
    
    # CALCULATOR
    ("Calculate the monthly payment for a $500k mortgage at 6%", IntentType.CALCULATOR),
    ("What is 15% of 850?", IntentType.CALCULATOR),
    ("If I invest $1000 monthly for 10 years at 7%, what is the future value?", IntentType.CALCULATOR),
    
    # GENERAL
    ("Hello, how are you?", IntentType.GENERAL),
    ("Who are you?", IntentType.GENERAL),
]

@pytest.mark.asyncio
@pytest.mark.parametrize("query, expected_intent", TEST_CASES)
async def test_router_accuracy(query, expected_intent):
    """Verify semantic router classifies specific queries correctly."""
    decision = await classify_intent(query)
    
    # Assert
    assert decision.intent == expected_intent, \
        f"Failed for query '{query}'. Expected {expected_intent}, got {decision.intent}. Reason: {decision.reasoning}"
