import pytest
import jwt
import os
from fastapi import HTTPException
from unittest.mock import patch, MagicMock

# Mock env vars before importing logic
with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": "test-secret"}):
    from Auth.verification import verify_token
    from Auth.dependencies import get_current_user

SECRET = "test-secret"

def create_test_token(payload=None, secret=SECRET):
    if payload is None:
        payload = {"sub": "user_123", "aud": "authenticated", "exp": 9999999999}
    return jwt.encode(payload, secret, algorithm="HS256")

def test_verify_valid_token():
    token = create_test_token()
    payload = verify_token(token)
    assert payload["sub"] == "user_123"

def test_verify_expired_token():
    # Expired in past
    token = create_test_token({"sub": "user_123", "exp": 1}, secret=SECRET)
    with pytest.raises(HTTPException) as exc:
        verify_token(token)
    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail

def test_verify_invalid_signature():
    # Signed with wrong key
    token = create_test_token(secret="wrong-key")
    with pytest.raises(HTTPException) as exc:
        verify_token(token)
    assert exc.value.status_code == 401
    assert "Invalid token" in exc.value.detail or "Signature verification failed" in str(exc.value.detail)

def test_dependency_valid():
    token = create_test_token()
    mock_creds = MagicMock()
    mock_creds.credentials = token
    
    user = get_current_user(mock_creds)
    assert user["sub"] == "user_123"
