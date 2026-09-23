import base64
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Union

import bcrypt
from cryptography.fernet import Fernet, InvalidToken
from jose import jwt, JWTError
from app.config import settings

def _fernet() -> Fernet:
    digest = hashlib.sha256(settings.JWT_SECRET_KEY.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))

def encrypt_secret(value: str) -> str:
    if not value:
        return ""
    return "fernet:" + _fernet().encrypt(value.encode("utf-8")).decode("utf-8")

def decrypt_secret(value: str) -> str:
    if not value:
        return ""
    if not value.startswith("fernet:"):
        return value
    try:
        return _fernet().decrypt(value.removeprefix("fernet:").encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""

def _bcrypt_encode(password: str) -> bytes:
    # bcrypt 仅使用前 72 字节，超出会直接抛 ValueError；我们主动按字节截断。
    return password.encode("utf-8")[:72]


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_bcrypt_encode(plain_password), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_bcrypt_encode(password), bcrypt.gensalt()).decode("utf-8")

def create_access_token(subject: Union[str, Any], expires_delta: Union[timedelta, None] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "access"
    }
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def create_refresh_token(subject: Union[str, Any], expires_delta: Union[timedelta, None] = None) -> str:
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    
    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "refresh"
    }
    encoded_jwt = jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded_jwt

def verify_token(token: str) -> Union[str, None]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        token_type = payload.get("type")
        if token_type != "access":
            return None
        token_subject = payload.get("sub")
        if token_subject is None:
            return None
        return token_subject
    except JWTError:
        return None

def verify_refresh_token(token: str) -> Union[str, None]:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        token_type = payload.get("type")
        if token_type != "refresh":
            return None
        token_subject = payload.get("sub")
        if token_subject is None:
            return None
        return token_subject
    except JWTError:
        return None
