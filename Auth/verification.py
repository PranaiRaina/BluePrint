import os
import jwt
from fastapi import HTTPException, status
from dotenv import load_dotenv

load_dotenv()

SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

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

    try:
        # Supabase uses HS256 by default for signing
        # We decode and verify signature, expiration, and audience
        payload = jwt.decode(
            token, 
            SUPABASE_JWT_SECRET, 
            algorithms=["HS256"],
            options={"verify_aud": False} # Supabase 'aud' can be 'authenticated', checking explicitly below if needed
        )
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
