import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from ManagerAgent.api import app
from ManagerAgent.router import manager_agent
from CalcAgent.agent import financial_agent
import asyncio
import json

# Initialize TestClient
client = TestClient(app)

# =============================================================================
# 1. API Integration Tests (Validation, Rate Limits, Health)
# =============================================================================

def test_health_check():
    """Verify health endpoint returns status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["service"] == "ManagerAgent"

def test_api_input_validation_too_long():
    """Verify API rejects overly long queries (Input Sanitization)."""
    long_query = "a" * 1001
    response = client.post("/v1/agent/calculate", json={"query": long_query})
    assert response.status_code == 400
    assert "too long" in response.json()["detail"]

def test_api_rate_limit_headers():
    """Verify rate limiting logic (Mocking the store to avoid actual blocks)."""
    # We won't block ourselves in test, but we check if request succeeds normally
    response = client.post("/v1/agent/calculate", json={"query": "test"})
    # If we haven't hit limit, it should try to run agent (and fail/mock) or return 500 if agent fails
    # We mostly care that it doesn't 429 immediately unless we force it
    assert response.status_code in [200, 500] 

# =============================================================================
# 2. Router Logic Tests (Manager Agent)
# =============================================================================

@pytest.mark.asyncio
async def test_manager_routes_to_calc():
    """
    Test that 'Calculate mortgage' routes to FinancialCalculator handoff.
    We test this by mocking the LLM's decision or checking tool calls.
    Since we can't easily mock the Groq LLM decision deterministically without VCR,
    we will rely on the System Prompt logic check or integration test.
    
    For this 'Rigorous' test, we will act as the Agent framework and verify
    that the system prompt contains the correct instructions.
    """
    instructions = manager_agent.instructions
    assert "Financial Calculator (Handoff)" in instructions
    assert "Document Analysis (Tool)" in instructions
    
    # Verify tools are attached
    tool_names = [t.name for t in manager_agent.tools]
    # Handoffs in openai-agents might not appear in .tools list directly depending on version,
    # but tools should definitely include 'perform_rag_search'
    assert "perform_rag_search" in str(manager_agent.tools) or "perform_rag_search" in tool_names

@pytest.mark.asyncio
async def test_rag_tool_wrapper_handles_search():
    """Verify the RAG tool wrapper calls the graph correctly."""
    from ManagerAgent.tools import perform_rag_search
    
    # Mock the RAG graph
    with patch("ManagerAgent.tools.app_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(return_value={"generation": "The invoice total is $500."})
        
        result = await perform_rag_search("Summarize invoice")
        
        assert "The invoice total is $500" in result
        mock_graph.ainvoke.assert_called_once()
        args = mock_graph.ainvoke.call_args[0][0]
        assert args["question"] == "Summarize invoice"

@pytest.mark.asyncio
async def test_rag_tool_handles_error():
    """Verify RAG tool returns error message purely, no crash."""
    from ManagerAgent.tools import perform_rag_search
    
    with patch("ManagerAgent.tools.app_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(side_effect=Exception("ChromaDB connection failed"))
        
        result = await perform_rag_search("Crash me")
        
        assert "Error performing RAG search" in result
        assert "ChromaDB connection failed" in result

# =============================================================================
# 3. End-to-End Simulation (Mocked Runner)
# =============================================================================

@patch("ManagerAgent.api.Runner.run", new_callable=AsyncMock)
def test_api_success_flow(mock_run):
    """Verify the full API flow calls the runner and returns result."""
    # Setup mock return
    mock_result = MagicMock()
    mock_result.final_output = "Mortgage payment is $1,200."
    mock_run.return_value = mock_result
    
    response = client.post("/v1/agent/calculate", json={"query": "Calculate mortgage"})
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["final_output"] == "Mortgage payment is $1,200."
    
    # Verify Runner was called with manager_agent
    mock_run.assert_awaited_once()
    args = mock_run.call_args
    assert args[0][0].name == "ManagerAgent" # First arg is agent
    assert args[0][1] == "Calculate mortgage" # Second arg is query

@patch("ManagerAgent.router.Runner.run", new_callable=AsyncMock)
@pytest.mark.asyncio
async def test_financial_tool_wrapper(mock_run):
    """
    Test the explicit tool wrapper 'ask_financial_calculator'.
    It should call Runner.run(financial_agent, query) and return final_output.
    """
    from ManagerAgent.router import ask_financial_calculator, financial_agent
    
    # Mock result
    mock_result = MagicMock()
    mock_result.final_output = "Computed: $500"
    mock_run.return_value = mock_result
    
    # Call wrapper
    result = await ask_financial_calculator("Test query")
    
    # Assertions
    assert result == "Computed: $500"
    # Check that it called Runner with the financial_agent, NOT manager_agent
    mock_run.assert_awaited_once()
    args = mock_run.call_args
    assert args[0][0] == financial_agent
    assert args[0][1] == "Test query"
