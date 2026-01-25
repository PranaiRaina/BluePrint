import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from ManagerAgent.api import app, init_db, DB_PATH
import os
import sqlite3

client = TestClient(app)

# Ensure fresh DB for tests
@pytest.fixture(autouse=True)
def setup_db():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    init_db()
    yield
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

@patch("ManagerAgent.api.Runner.run", new_callable=AsyncMock)
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
    
    response1 = client.post("/v1/agent/calculate", json={
        "query": "My tax rate is 20%",
        "session_id": session_id
    })
    assert response1.status_code == 200
    
    # Check that Runner was called with just the query (since history was empty)
    args1 = mock_run.call_args_list[0]
    # args1[0][1] is the query argument passed to Runner.run(agent, query)
    assert "My tax rate is 20%" in args1[0][1]
    
    # --- Turn 2: User asks question relying on info ---
    mock_result_2 = MagicMock()
    mock_result_2.final_output = "Your tax rate is 20%."
    mock_run.return_value = mock_result_2
    
    response2 = client.post("/v1/agent/calculate", json={
        "query": "What is my tax rate?",
        "session_id": session_id
    })
    assert response2.status_code == 200
    
    # Check that Runner was called WITH history injected
    args2 = mock_run.call_args_list[1]
    last_query_arg = args2[0][1]
    
    print(f"Captured Query passed to Agent:\n{last_query_arg}")
    
    assert "Previous conversation:" in last_query_arg
    assert "User: My tax rate is 20%" in last_query_arg
    assert "Agent: Understood, your tax rate is 20%." in last_query_arg
    assert "Current User Query: What is my tax rate?" in last_query_arg
