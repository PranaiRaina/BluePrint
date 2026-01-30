from fastapi.testclient import TestClient
from ManagerAgent.api import app
from Auth.dependencies import get_current_user

client = TestClient(app)


def test_calculate_endpoint_integration():
    """
    Integration test for POST /v1/agent/calculate.
    Verifies that the API accepts the request, authenticates (mocked),
    and returns a valid response from the Agent.
    """
    # Override authentication to bypass real token verification
    app.dependency_overrides[get_current_user] = lambda: {"sub": "test_user_id"}

    payload = {
        "query": "What is 100 * 5?",  # Simple Calc query
        "session_id": "test_session_integration",
    }

    response = client.post("/v1/agent/calculate", json=payload)

    # Check status code
    assert response.status_code == 200, f"API Failed with {response.text}"

    # Check response structure
    data = response.json()
    assert "final_output" in data
    assert "status" in data
    assert data["status"] == "success"

    # Check content (Gemini response might vary slightly, but should contain 500)
    assert "500" in data["final_output"], (
        f"Expected 500 in output, got: {data['final_output']}"
    )

    # Cleanup overrides
    app.dependency_overrides = {}
