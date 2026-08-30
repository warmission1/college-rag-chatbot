import bcrypt
from datetime import datetime, timedelta
from typing import Any, Optional, Union
from jose import jwt, JWTError
from backend.app.core.config import settings


def get_jwt_secret() -> str:
    secret = settings.AUTH_SECRET.strip()
    return secret if secret else "college_rag_default_dev_secret_key_2026"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        if isinstance(hashed_password, str):
            hashed_bytes = hashed_password.encode("utf-8")
        else:
            hashed_bytes = hashed_password
        return bcrypt.checkpw(plain_password.encode("utf-8")[:72], hashed_bytes)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    pw_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pw_bytes, salt).decode("utf-8")


def create_access_token(subject: Union[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {"exp": expire, "sub": str(subject)}
    return jwt.encode(to_encode, get_jwt_secret(), algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Optional[str]:
    try:
        payload = jwt.decode(token, get_jwt_secret(), algorithms=[settings.ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None
