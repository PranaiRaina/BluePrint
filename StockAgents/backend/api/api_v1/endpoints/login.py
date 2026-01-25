from datetime import timedelta
from typing import Any
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from core import security
from core.config import settings

router = APIRouter()

@router.post("/login/access-token")
def login_access_token(form_data: OAuth2PasswordRequestForm = Depends()) -> Any:
    """
    OAuth2 compatible token login, get an access token for future requests.
    """
    # Verify user (Mock verification for now)
    # user = authenticate(form_data.username, form_data.password) 
    # if not user: ...
    
    # Mock behavior: Accept any 'admin' user or if password is 'password'
    if form_data.username != "admin" or form_data.password != "password":
         raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": security.create_access_token(
            subject=form_data.username, expires_delta=access_token_expires
        ),
        "token_type": "bearer",
    }
