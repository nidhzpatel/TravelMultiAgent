import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, validate_production_settings
from app.security.middleware import SecurityHeadersMiddleware
from app.security.limits import InMemoryRateLimiter, RateLimitExceeded
from app.security.logging import SecretRedactionFilter


class SecurityConfigTests(unittest.TestCase):
    def test_production_requires_postgres_and_oidc(self) -> None:
        with self.assertRaises(RuntimeError):
            validate_production_settings(Settings(environment="production"))
        validate_production_settings(
            Settings(
                environment="production",
                database_url="postgresql+psycopg://user:pass@db/voyagemind",
                oidc_issuer="https://issuer.example",
                oidc_audience="voyagemind-api",
                oidc_jwks_url="https://issuer.example/.well-known/jwks.json",
                cors_origins=["https://app.example"],
            )
        )

    def test_security_headers_are_present(self) -> None:
        app = FastAPI()
        app.add_middleware(SecurityHeadersMiddleware)

        @app.get("/")
        def root() -> dict[str, bool]:
            return {"ok": True}

        response = TestClient(app).get("/")
        self.assertEqual(response.headers["x-content-type-options"], "nosniff")
        self.assertEqual(response.headers["x-frame-options"], "DENY")

    def test_rate_limit_and_secret_redaction(self) -> None:
        limiter = InMemoryRateLimiter(limit=2, window_seconds=60)
        limiter.check("user", now=10)
        limiter.check("user", now=11)
        with self.assertRaises(RateLimitExceeded):
            limiter.check("user", now=12)
        record = __import__("logging").LogRecord("test", 20, "", 0, "Bearer abc token=secret", (), None)
        SecretRedactionFilter().filter(record)
        self.assertEqual(record.msg, "Bearer [REDACTED] token=[REDACTED]")
