import pytest
from unittest.mock import patch, MagicMock
from ManagerAgent.router_intelligence import classify_intent, IntentType


# Mock response structure for LiteLLM
class MockChoice:
    def __init__(self, content):
        self.message = MagicMock()
        self.message.content = content


class MockResponse:
    def __init__(self, content):
        self.choices = [MockChoice(content)]


@pytest.mark.asyncio
async def test_classify_stock_intent():
    """Test classification of stock queries."""
    mock_json = '{"intents": ["stock"], "primary_intent": "stock", "extracted_tickers": [], "reasoning": "User asked for price"}'

    with patch("ManagerAgent.router_intelligence.completion") as mock_completion:
        mock_completion.return_value = MockResponse(mock_json)

        decision = await classify_intent("What is the price of Apple?")

        assert decision.primary_intent == IntentType.STOCK
        assert decision.reasoning == "User asked for price"


@pytest.mark.asyncio
async def test_classify_rag_intent():
    """Test classification of RAG queries."""
    mock_json = '{"intents": ["rag"], "primary_intent": "rag", "extracted_tickers": [], "reasoning": "User referenced uploaded file"}'

    with patch("ManagerAgent.router_intelligence.completion") as mock_completion:
        mock_completion.return_value = MockResponse(mock_json)

        decision = await classify_intent("What does my PDF say about Apple?")

        assert decision.primary_intent == IntentType.RAG


@pytest.mark.asyncio
async def test_classify_calculator_intent():
    """Test classification of calculator queries."""
    mock_json = '{"intents": ["calculator"], "primary_intent": "calculator", "extracted_tickers": [], "reasoning": "User asking for tax math"}'

    with patch("ManagerAgent.router_intelligence.completion") as mock_completion:
        mock_completion.return_value = MockResponse(mock_json)

        decision = await classify_intent("Calculate tax on $100k")

        assert decision.primary_intent == IntentType.CALCULATOR


@pytest.mark.asyncio
async def test_classify_error_handling():
    """Test fallback to GENERAL on error."""
    with patch("ManagerAgent.router_intelligence.completion") as mock_completion:
        mock_completion.side_effect = Exception("API Error")

        decision = await classify_intent("Hello")

        assert decision.primary_intent == IntentType.GENERAL
        assert "Error" in decision.reasoning
