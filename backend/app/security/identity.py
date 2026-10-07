from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Cookie, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import get_settings
from app.security.limits import InMemoryRateLimiter, RateLimitExceeded
from app.persistence.repositories import QuotaExceededError, SqlAlchemyTripRepository


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


def current_principal(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    vm_session: str | None = Cookie(default=None),
) -> Principal:
    if credentials is None and not vm_session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    if vm_session:
        secret = get_settings().session_secret
        if len(secret) < 32:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")
        try:
            claims = jwt.decode(vm_session, secret, algorithms=["HS256"])
            subject = claims.get("sub")
            if not isinstance(subject, str) or not subject:
                raise ValueError("Session subject is missing")
            email = claims.get("email")
            return Principal(subject=subject, email=email if isinstance(email, str) else None)
        except (ValueError, jwt.PyJWTError) as exc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session") from exc
    try:
        return token_verifier().verify(credentials.credentials)
    except (RuntimeError, ValueError, jwt.PyJWTError) as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token") from exc


def enforce_rate_limit(principal: Principal = Depends(current_principal)) -> None:
    try:
        database_url = get_settings().database_url
        if database_url:
            SqlAlchemyTripRepository(database_url).consume_quota(principal.subject, get_settings().rate_limit_per_minute)
        else:
            rate_limiter().check(principal.subject)
    except (RateLimitExceeded, QuotaExceededError) as exc:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded") from exc
