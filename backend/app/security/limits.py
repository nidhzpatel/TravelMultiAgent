from __future__ import annotations

import time
from collections import defaultdict, deque


class RateLimitExceeded(Exception):
    pass


class InMemoryRateLimiter:
    """Bounded local limiter; replace with a shared store when API replicas are enabled."""

    def __init__(self, limit: int = 60, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str, now: float | None = None) -> None:
        now = now if now is not None else time.monotonic()
        events = self._events[key]
        while events and events[0] <= now - self.window_seconds:
            events.popleft()
        if len(events) >= self.limit:
            raise RateLimitExceeded("Rate limit exceeded")
        events.append(now)
