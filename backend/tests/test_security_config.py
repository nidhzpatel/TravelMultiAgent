import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import Settings, validate_production_settings
from app.security.middleware import SecurityHeadersMiddleware


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
