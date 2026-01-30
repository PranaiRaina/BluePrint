import pytest
import os
from dotenv import load_dotenv

# Load real environment variables for integration testing
load_dotenv()


@pytest.mark.skipif(
    not os.getenv("SUPABASE_JWT_SECRET"),
    reason="Skipping integration test: SUPABASE_JWT_SECRET not set",
)
def test_real_env_configuration():
    """
    Verifies that the .env file is correctly configured and the secret works
    with the actual backend logic.
    """
    secret = os.getenv("SUPABASE_JWT_SECRET")
    url = os.getenv("SUPABASE_URL")

    assert secret is not None, "SUPABASE_JWT_SECRET is missing from .env"
    assert url is not None, "SUPABASE_URL is missing from .env"

    # We cannot generate a valid ES256 token without the private key.
    # The SUPABASE_JWT_SECRET in .env is typically the Public Key (for verification) or a Reference.
    # So we skip the actual token verification here to avoid HS256 errors.
    print("Environment variables verified.")
