import hashlib
from datetime import UTC, datetime, timedelta
from hmac import compare_digest
from typing import Any
from uuid import UUID

import jwt
from fastapi import HTTPException, status

from app.core.config import get_settings


def hash_password(password: str) -> str:
    secret = get_settings().jwt_secret.encode('utf-8')
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), secret, 120_000).hex()


def verify_password(password: str, password_hash: str) -> bool:
    return compare_digest(hash_password(password), password_hash)


def create_token(subject: UUID | str, token_type: str, expires_delta: timedelta, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        'sub': str(subject),
        'typ': token_type,
        'iss': settings.jwt_issuer,
        'iat': int(now.timestamp()),
        'exp': int((now + expires_delta).timestamp()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm='HS256')


def decode_token(token: str, expected_type: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=['HS256'], issuer=settings.jwt_issuer)
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token') from exc
    if payload.get('typ') != expected_type:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid token type')
    return payload
