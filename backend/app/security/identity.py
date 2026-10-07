from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.security.limits import InMemoryRateLimiter, RateLimitExceeded


@dataclass(frozen=True)
class Principal:
    subject: str
    email: str | None = None


class OidcTokenVerifier:
    def __init__(self, issuer: str, audience: str, jwks_url: str) -> None:
        self.issuer = issuer
        self.audience = audience
        self.jwks = jwt.PyJWKClient(jwks_url)

    def verify(self, token: str) -> Principal:
        signing_key = self.jwks.get_signing_key_from_jwt(token).key
        claims = jwt.decode(token, signing_key, algorithms=["RS256"], audience=self.audience, issuer=self.issuer)
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise ValueError("Token subject is missing")
        email = claims.get("email")
        return Principal(subject=subject, email=email if isinstance(email, str) else None)


@lru_cache
def token_verifier() -> OidcTokenVerifier:
    settings = get_settings()
    if not (settings.oidc_issuer and settings.oidc_audience and settings.oidc_jwks_url):
        raise RuntimeError("OIDC issuer, audience, and JWKS URL must be configured")
    return OidcTokenVerifier(settings.oidc_issuer, settings.oidc_audience, settings.oidc_jwks_url)


bearer = HTTPBearer(auto_error=False)


@lru_cache
def rate_limiter() -> InMemoryRateLimiter:
    return InMemoryRateLimiter(limit=get_settings().rate_limit_per_minute)


def current_principal(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Principal:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    try:
        return token_verifier().verify(credentials.credentials)
    except (RuntimeError, ValueError, jwt.PyJWTError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token") from exc


def enforce_rate_limit(principal: Principal = Depends(current_principal)) -> None:
    try:
        rate_limiter().check(principal.subject)
    except RateLimitExceeded as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded") from exc
