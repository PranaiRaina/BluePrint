import pytest
import jwt
import os
from fastapi import HTTPException
from unittest.mock import patch, MagicMock
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

# Generate a temporary EC key pair for testing
private_key_obj = ec.generate_private_key(ec.SECP256R1())
public_key_obj = private_key_obj.public_key()

# Serialize to PEM format
PRIVATE_PEM = private_key_obj.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)

PUBLIC_PEM = public_key_obj.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)

# Mock env vars with the PUBLIC KEY for verification
with patch.dict(os.environ, {"SUPABASE_JWT_SECRET": PUBLIC_PEM.decode("utf-8")}):
    from Auth import verification
    from Auth.dependencies import get_current_user

    # FORCE OVERRIDE CLEAN_PEM to ensure it matches our test key
    # (In case module-level logic stripped it weirdly or read old env)
    verification.CLEAN_PEM = PUBLIC_PEM.decode("utf-8")
    from Auth.verification import verify_token


def create_test_token(payload=None, private_key=PRIVATE_PEM):
    if payload is None:
        payload = {"sub": "user_123", "aud": "authenticated", "exp": 9999999999}

    return jwt.encode(payload, private_key, algorithm="ES256")


def test_verify_valid_token():
    token = create_test_token()
    # We patch CLEAN_PEM inside verify_token implicitly by mocking env var import
    # But verify_token reads CLEAN_PEM at module level.
    # Since we imported AFTER patch, it should have the Public Key.

    # However, verify_token logic might strip headers/formatting.
    # Let's verify it works with the patched import.
    payload = verify_token(token)
    assert payload["sub"] == "user_123"


def test_verify_expired_token():
    # Expired in past
    token = create_test_token({"sub": "user_123", "exp": 1})
    with pytest.raises(HTTPException) as exc:
        verify_token(token)
    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail


def test_verify_invalid_signature():
    # Signed with a DIFFERENT private key
    other_private_key = ec.generate_private_key(ec.SECP256R1())
    other_pem = other_private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    token = create_test_token(private_key=other_pem)
    with pytest.raises(HTTPException) as exc:
        verify_token(token)
    assert exc.value.status_code == 401
    # Error message varies (Signature verification failed or Invalid token)


def test_dependency_valid():
    token = create_test_token()
    mock_creds = MagicMock()
    mock_creds.credentials = token

    user = get_current_user(mock_creds)
    assert user["sub"] == "user_123"
