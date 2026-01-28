import os
import jwt
from fastapi import HTTPException, status
from dotenv import load_dotenv

load_dotenv()

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")
SUPABASE_JWT_PUBLIC_KEY = os.getenv("SUPABASE_JWT_PUBLIC_KEY", "")
SUPABASE_URL = os.getenv("SUPABASE_URL")

# --- Robust PEM Cleaning ---
# In case the .env value has quotes or escaped newlines
CLEAN_PEM = SUPABASE_JWT_PUBLIC_KEY.strip().strip('"').strip("'")
print(f"DEBUG: JWT Public Key Length: {len(SUPABASE_JWT_PUBLIC_KEY)}")
print(f"DEBUG: Clean PEM Starts With: {repr(CLEAN_PEM[:30])}")

# If it look like a PEM but is missing newlines (common in .env), restore them
if CLEAN_PEM.startswith("-----BEGIN PUBLIC KEY-----") and "\n" not in CLEAN_PEM:
    print("DEBUG: Restoring newlines to PEM")
    CLEAN_PEM = CLEAN_PEM.replace("-----BEGIN PUBLIC KEY-----", "-----BEGIN PUBLIC KEY-----\n")
    CLEAN_PEM = CLEAN_PEM.replace("-----END PUBLIC KEY-----", "\n-----END PUBLIC KEY-----")

# Production-grade JWK Client for ES256 (Fallback)
jwks_client = None
if SUPABASE_URL:
    try:
        # Standard Supabase path for Public JSON Web Key Sets
        jwks_url = f"{SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        print(f"DEBUG: JWKS URL: {jwks_url}")
        jwks_client = jwt.PyJWKClient(jwks_url)
    except Exception as e:
        print(f"WARNING: Could not initialize JWKS client: {e}")

def verify_token(token: str) -> dict:
    """
    Verifies a Supabase JWT token using the project's JWT secret.
    
    Args:
        token (str): The Bearer token string.
        
    Returns:
        dict: The decoded token payload if valid.
        
    Raises:
        HTTPException: If token is invalid, expired, or missing signature.
    """
    if not SUPABASE_JWT_SECRET:
        # Fail safe if secret is not configured
        print("ERROR: SUPABASE_JWT_SECRET is not set.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Server authentication configuration error."
        )

    # DEV MODE BYPASS
    if token == "mock-token":
        return {"sub": "dev-user-id", "aud": "authenticated", "email": "dev@example.com"}

    try:
        # 1. Inspect Header to determine algorithm
        unverified_header = jwt.get_unverified_header(token)
        alg = unverified_header.get("alg")
        print(f"DEBUG: Token Headers: {unverified_header}")
        
        # 2. Select appropriate verification method
        if alg == "ES256":
            # Check if we have a valid PEM Public Key (Modern/Production)
            if CLEAN_PEM.startswith("-----BEGIN PUBLIC KEY-----"):
                print("DEBUG: Using local PEM for ES256 verification")
                payload = jwt.decode(
                    token, 
                    CLEAN_PEM, 
                    algorithms=["ES256"], 
                    options={"verify_aud": False}
                )
            elif jwks_client:
                # FALLBACK: Try fetching from JWKS
                print("DEBUG: Falling back to JWKS fetch for ES256")
                signing_key = jwks_client.get_signing_key_from_jwt(token)
                payload = jwt.decode(
                    token, 
                    signing_key.key, 
                    algorithms=["ES256"], 
                    options={"verify_aud": False}
                )
            else:
                raise Exception("ES256 token received but no local Public Key or JWKS client available.")
        else:
            # LEGACY MODE: Uses HS256 with the shared secret
            # Use the raw secret from .env (not cleaned) for HS256 to avoid breaking it
            payload = jwt.decode(
                token, 
                SUPABASE_JWT_SECRET, 
                algorithms=["HS256"], 
                options={"verify_aud": False}
            )
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        # Catch all for JWT errors (InvalidSignature, SSL errors, etc.)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
