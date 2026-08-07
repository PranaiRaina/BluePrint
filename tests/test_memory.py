import pytest
from Auth.dependencies import get_current_user
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from ManagerAgent.api import app
from ManagerAgent.router_intelligence import IntentType, RouterDecision

client = TestClient(app)

app.dependency_overrides[get_current_user] = lambda: {
    "sub": "test_user",
    "email": "test@example.com",
}


@pytest.fixture(autouse=True)
def setup_auth():
    # The SQLite scaffolding this fixture used to do (patching DB_PATH, deleting
    # a test .db file, calling init_db) died with the Supabase migration -
    # DB_PATH and init_db no longer exist in ManagerAgent.api.
    app.dependency_overrides[get_current_user] = lambda: {
        "sub": "test_user",
        "email": "test@example.com",
    }

    yield

    app.dependency_overrides = {}


@pytest.fixture(autouse=True)
def fake_history_store():
    """In-memory stand-in for the Postgres history layer and the LLM router.

    This test asks one question: does a previous turn reach the agent's prompt?
    Postgres is only the transport, and the router only picks a branch. Faking
    both keeps the test offline and deterministic - and it is why the test used
    to fail, since "test_user" is not a valid Postgres uuid.
    """
    turns: list[tuple[str, str]] = []

    def fake_save(user_id, session_id, user_query, agent_response):
        turns.append(("User", user_query))
        turns.append(("Agent", agent_response))

    def fake_get(user_id, session_id, limit=10):
        return "\n".join(f"{role}: {content}" for role, content in turns)

    async def fake_classify(query):
        return RouterDecision(
            intents=[IntentType.GENERAL],
            primary_intent=IntentType.GENERAL,
            extracted_tickers=[],
            reasoning="stubbed for test",
        )

    with (
        patch("ManagerAgent.api.save_chat_pair", side_effect=fake_save),
        patch("ManagerAgent.api.get_chat_history", side_effect=fake_get),
        patch("ManagerAgent.api.classify_intent", side_effect=fake_classify),
    ):
        yield


@patch("ManagerAgent.api.run_with_retry", new_callable=AsyncMock)
def test_memory_persistence(mock_run):
    """
    Test that the agent 'remembers' context by checking if history is injected.
    We mock Runner.run to verify the input prompt contains previous history.
    """
    session_id = "test_memory_1"

    # --- Turn 1: User provides info ---
    mock_result_1 = MagicMock()
    mock_result_1.final_output = "Understood, your tax rate is 20%."
    mock_run.return_value = mock_result_1

    response1 = client.post(
        "/v1/agent/calculate",
        json={"query": "My tax rate is 20%", "session_id": session_id},
    )
    assert response1.status_code == 200

    # Check that Runner was called with just the query (since history was empty)
    args1 = mock_run.call_args_list[0]
    # args1[0][1] is the query argument passed to Runner.run(agent, query)
    assert "My tax rate is 20%" in args1[0][1]

    # --- Turn 2: User asks question relying on info ---
    mock_result_2 = MagicMock()
    mock_result_2.final_output = "Your tax rate is 20%."
    mock_run.return_value = mock_result_2

    response2 = client.post(
        "/v1/agent/calculate",
        json={"query": "What is my tax rate?", "session_id": session_id},
    )
    assert response2.status_code == 200

    # Check that Runner was called WITH history injected
    args2 = mock_run.call_args_list[1]
    last_query_arg = args2[0][1]

    print(f"Captured Query passed to Agent:\n{last_query_arg}")

    assert "Previous conversation:" in last_query_arg
    assert "User: My tax rate is 20%" in last_query_arg
    assert "Agent: Understood, your tax rate is 20%." in last_query_arg
    assert "Current User Query: What is my tax rate?" in last_query_arg
