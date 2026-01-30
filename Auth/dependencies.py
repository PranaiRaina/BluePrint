from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from Auth.verification import verify_token

# Define the security scheme
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    """
    FastAPI dependency that extracts and verifies the Bearer token.
    Returns the user payload (claims) if valid.
    """
    token = credentials.credentials
    try:
        payload = verify_token(token)
        return payload
    except Exception as e:
        print(f"Auth verification failed: {e}")
        raise HTTPException(
            status_code=401,
            detail=f"Authentication failed: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
