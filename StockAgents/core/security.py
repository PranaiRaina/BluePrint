from datetime import datetime, timedelta
from typing import Any, Union
from jose import jwt
from passlib.context import CryptContext
from cryptography.fernet import Fernet
import base64
import os
from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# AES-256 Encryption Setup
# In production, this key should be loaded from a secure vault
# We derive a Fernet key from the SECRET_KEY for demonstration, 
# but ideally, store a separate 32-url-safe-base64-encoded key.
def _get_fernet_key():
    # Pad or truncate the secret key to 32 bytes for base64 encoding
    key = settings.SECRET_KEY.encode()
    if len(key) < 32:
        key = key.ljust(32, b'0')
    else:
        key = key[:32]
    return base64.urlsafe_b64encode(key)

cipher_suite = Fernet(_get_fernet_key())

def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"sub": str(subject), "exp": expire}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def encrypt_data(data: str) -> str:
    """Encrypts a string using AES (Fernet) and returns a url-safe base64 string."""
    if not data:
        return ""
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(token: str) -> str:
    """Decrypts a token."""
    if not token:
        return ""
    return cipher_suite.decrypt(token.encode()).decode()
