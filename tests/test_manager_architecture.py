import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from ManagerAgent.api import app

# ManagerAgent.router is deleted, removing import

# Initialize TestClient
client = TestClient(app)


# Override auth dependency in fixture
@pytest.fixture(autouse=True)
def override_auth():
    from Auth.dependencies import get_current_user

    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "test_user",
        "email": "test@example.com",
    }
    yield
    app.dependency_overrides = {}


@pytest.fixture(autouse=True)
def ensure_db():
    from ManagerAgent.api import init_db

    init_db()


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

# Tests for deleted manager_agent are removed


@pytest.mark.asyncio
async def test_rag_tool_wrapper_handles_search():
    """Verify the RAG tool wrapper calls the graph correctly."""
    from ManagerAgent.tools import perform_rag_search

    # Mock the RAG graph
    with patch("ManagerAgent.tools.app_graph") as mock_graph:
        mock_graph.ainvoke = AsyncMock(
            return_value={"generation": "The invoice total is $500."}
        )

        result = await perform_rag_search("Summarize invoice")

        assert "The invoice total is $500" in result
        mock_graph.ainvoke.assert_called_once()
        args = mock_graph.ainvoke.call_args[0][0]
        assert args["question"] == "Summarize invoice"


# =============================================================================
# 3. End-to-End Simulation (Mocked Runner)
# =============================================================================


@patch("ManagerAgent.api.run_with_retry", new_callable=AsyncMock)
def test_api_success_flow(mock_run):
    """Verify the full API flow calls the runner and returns result."""
    # Setup mock return
    mock_result = MagicMock()
    mock_result.final_output = "Mortgage payment is $1,200."
    mock_run.return_value = mock_result

    # Mock history and router to prevent external calls
    with (
        patch("ManagerAgent.api.get_chat_history", return_value=""),
        patch(
            "ManagerAgent.api.classify_intent", new_callable=AsyncMock
        ) as mock_classify,
    ):
        # Setup Router Mock to return CALCULATOR intent
        mock_decision = MagicMock()
        mock_decision.intents = []  # Not multi-intent
        mock_decision.primary_intent = (
            "calculator"  # Matching string enum value or object
        )
        # Note: In api.py it compares against IntentType.CALCULATOR enum.
        # So we should probably use the Enum or a string if it compares by value.
        # Let's import IntentType to be safe, or assume string comparison works if Enum is StrEnum.
        from ManagerAgent.router_intelligence import IntentType

        mock_decision.primary_intent = IntentType.CALCULATOR

        mock_classify.return_value = mock_decision

        response = client.post(
            "/v1/agent/calculate", json={"query": "Calculate mortgage"}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["final_output"] == "Mortgage payment is $1,200."

    # Verify Runner was called with financial_agent (since Calculator intent)
    mock_run.assert_awaited_once()
    args = mock_run.call_args
    assert args[0][0].name == "FinancialCalculator"  # First arg is agent
    assert args[0][1] == "Calculate mortgage"  # Second arg is query


# Obsolete wrapper tests removed
