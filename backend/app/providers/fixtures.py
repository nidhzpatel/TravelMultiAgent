"""Explicit development-only provider fixtures."""

from app.providers.base import ProviderCapabilities


class DevelopmentFixture:
    capabilities = ProviderCapabilities(live=False)

    def __init__(self, environment: str) -> None:
        if environment == "production":
            raise RuntimeError("Development fixtures are disabled in production")
