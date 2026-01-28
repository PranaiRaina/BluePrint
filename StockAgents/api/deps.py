from typing import Generator
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from pydantic import ValidationError

from core import security
from core.config import settings
# from models.user import User # TODO: Create User model

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/login/access-token")

class TokenPayload:
    def __init__(self, sub: str = None):
        self.sub = sub

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        token_data = TokenPayload(sub=user_id)
    except (JWTError, ValidationError):
        raise credentials_exception
    
    # TODO: Fetch user from DB
    # user = crud.user.get(db, id=token_data.sub)
    # if not user:
    #     raise credentials_exception
    # return user
    return token_data # Returning payload for now until DB is set up
