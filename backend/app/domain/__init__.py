"""Versioned v2 business contracts.

The domain package contains no HTTP, ORM, provider, or agent dependencies.
"""

from app.domain.contracts import Trip, TripVersion

__all__ = ["Trip", "TripVersion"]
