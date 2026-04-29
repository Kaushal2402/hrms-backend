from datetime import datetime, timedelta
from typing import Any, Union, Optional
from jose import jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def verify_password(plain_password: str, hashed_password: str) -> bool:
    # Bcrypt has a limit of 72 bytes. We must encode to ensure we are counting bytes.
    # Passlib might handle str automatically but if we want to truncate, we must do it on bytes.
    # However, passlib expects str usually if using default context, but let's be safe.
    # Actually, passlib with bcrypt backend handles unicode, but the limit is 72 *bytes*.
    # So if "password" is 80 chars, encoding it -> 80 bytes.
    
    # We will try to pass strings but ensure they are short enough in BYTES.
    if len(plain_password.encode('utf-8')) > 72:
         # Use only the first 72 bytes decoded back to ignore trailing partial chars? 
         # Or simpler: just use a hash of the password if it's too long?
         # Standard approach: SHA256 before Bcrypt if > 72 bytes.
         # But sticking to truncation for now as requested:
         max_bytes = 72
         encoded = plain_password.encode('utf-8')
         if len(encoded) > max_bytes:
             plain_password = encoded[:max_bytes].decode('utf-8', 'ignore')

    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    # Bcrypt has a limit of 72 bytes
    if len(password.encode('utf-8')) > 72:
         max_bytes = 72
         encoded = password.encode('utf-8')
         if len(encoded) > max_bytes:
             password = encoded[:max_bytes].decode('utf-8', 'ignore')
             
    return pwd_context.hash(password)
