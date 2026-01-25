from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from Auth.verification import verify_token

# Define the security scheme
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    FastAPI dependency that extracts and verifies the Bearer token.
    Returns the user payload (claims) if valid.
    """
    token = credentials.credentials
    payload = verify_token(token)
    
    # You can add extra checks here, e.g., enforcing 'aud' claim
    # if payload.get("aud") != "authenticated":
    #    raise HTTPException(status_code=403, detail="Invalid audience")
        
    return payload
