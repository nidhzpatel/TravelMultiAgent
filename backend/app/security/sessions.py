from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import HTTPException, status

from app.config import get_settings
from app.security.identity import Principal


def create_session(principal: Principal) -> tuple[str, str]:
    secret = get_settings().session_secret
    if len(secret) < 32:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Session cookies are not configured")
    payload = {"sub": principal.subject, "email": principal.email, "exp": datetime.now(timezone.utc) + timedelta(hours=8)}
    return jwt.encode(payload, secret, algorithm="HS256"), secrets.token_urlsafe(32)
