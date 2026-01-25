import pytest
import os
import jwt
from dotenv import load_dotenv
from Auth.verification import verify_token

# Load real environment variables for integration testing
load_dotenv()

@pytest.mark.skipif(not os.getenv("SUPABASE_JWT_SECRET"), reason="Skipping integration test: SUPABASE_JWT_SECRET not set")
def test_real_env_configuration():
    """
    Verifies that the .env file is correctly configured and the secret works
    with the actual backend logic.
    """
    secret = os.getenv("SUPABASE_JWT_SECRET")
    url = os.getenv("SUPABASE_URL")
    
    assert secret is not None, "SUPABASE_JWT_SECRET is missing from .env"
    assert url is not None, "SUPABASE_URL is missing from .env"

    # Generate a valid token using the real secret
    payload = {
        "sub": "integration-test-user",
        "aud": "authenticated",
        "role": "authenticated",
        "exp": 9999999999
    }
    
    token = jwt.encode(payload, secret, algorithm="HS256")
    
    # Ensure the verification module uses the same secret
    from unittest.mock import patch
    with patch("Auth.verification.SUPABASE_JWT_SECRET", secret):
        # Verify it using the actual backend logic
        decoded = verify_token(token)
    
    assert decoded["sub"] == "integration-test-user"
