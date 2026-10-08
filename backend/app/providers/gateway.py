"""Bounded provider execution and cache isolation."""

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime, timedelta, timezone
from typing import Callable, Generic, TypeVar

from pydantic import BaseModel

from app.domain.contracts import ProviderOutcomeStatus
from app.providers.base import ProviderResult

T = TypeVar("T")


class ProviderGateway(Generic[T]):
    def __init__(self, timeout_seconds: float = 5.0, cache_ttl: timedelta = timedelta(minutes=5)) -> None:
        self.timeout_seconds = timeout_seconds
        self.cache_ttl = cache_ttl
        self._cache: dict[tuple[str, str], tuple[datetime, ProviderResult[T]]] = {}

    @staticmethod
    def _fingerprint(request: BaseModel) -> str:
        payload = json.dumps(request.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    def execute(self, provider_name: str, request: BaseModel, call: Callable[[], ProviderResult[T]]) -> ProviderResult[T]:
        key = (provider_name, self._fingerprint(request))
        cached = self._cache.get(key)
        now = datetime.now(timezone.utc)
        if cached and cached[0] > now:
            return cached[1]
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(call)
        try:
            result = future.result(timeout=self.timeout_seconds)
        except TimeoutError:
            future.cancel()
            return ProviderResult(status=ProviderOutcomeStatus.UNAVAILABLE, error_code="timeout")
        except Exception:
            return ProviderResult(status=ProviderOutcomeStatus.ERROR, error_code="provider_error")
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        values = result.value if isinstance(result.value, tuple) else (result.value,)
        expiries = [value.expires_at for value in values if value is not None and hasattr(value, "expires_at")]
        if expiries and min(expiries) <= now:
            return ProviderResult(status=ProviderOutcomeStatus.UNAVAILABLE, error_code="expired_result")
        if result.status in {ProviderOutcomeStatus.SUCCESS, ProviderOutcomeStatus.NO_RESULTS}:
            expiry = min([now + self.cache_ttl, *expiries]) if expiries else now + self.cache_ttl
            self._cache[key] = (expiry, result)
        return result


def select_provider(environment: str, live_provider: T | None, fixture_provider: T | None) -> T:
    if environment == "production":
        if live_provider is None:
            raise RuntimeError("A live provider is required in production")
        return live_provider
    if fixture_provider is None:
        raise RuntimeError("A development fixture provider is required")
    return fixture_provider
