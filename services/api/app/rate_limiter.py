"""
Per-principal rate limiting using an in-memory sliding window.
Enforces limits per org/user or client IP, returning 429 with
Retry-After, X-RateLimit-Limit, and X-RateLimit-Remaining headers.
"""
from __future__ import annotations

import time
from collections import defaultdict
from threading import Lock
from typing import Any

from fastapi import Depends, Request, Response

from app.auth import Principal, get_principal
from app.config import get_settings
from app.errors import rate_limited


class SlidingWindowLimiter:
    def __init__(self, limit: int = 120, window_seconds: int = 60) -> None:
        self.limit = limit
        self.window_seconds = window_seconds
        self._history: dict[str, list[float]] = defaultdict(list)
        self._lock = Lock()

    def check(self, key: str, custom_limit: int | None = None) -> tuple[bool, int, int]:
        """
        Check and record request.
        Returns: (allowed, remaining, retry_after)
        """
        now = time.time()
        cutoff = now - self.window_seconds
        limit = custom_limit if custom_limit is not None else self.limit

        with self._lock:
            timestamps = self._history[key]
            # Prune old timestamps
            self._history[key] = [t for t in timestamps if t > cutoff]
            current_count = len(self._history[key])

            if current_count >= limit:
                oldest = self._history[key][0]
                retry_after = max(1, int(oldest + self.window_seconds - now))
                return False, 0, retry_after

            self._history[key].append(now)
            remaining = max(0, limit - (current_count + 1))
            return True, remaining, 0

    def reset(self) -> None:
        with self._lock:
            self._history.clear()


GLOBAL_LIMITER = SlidingWindowLimiter(limit=120, window_seconds=60)


def rate_limit(limit: int = 120, window_seconds: int = 60):
    """Dependency factory for rate limiting."""
    limiter = SlidingWindowLimiter(limit=limit, window_seconds=window_seconds)

    async def _rate_limit_dep(
        request: Request,
        response: Response,
        principal: Principal | None = None,
    ) -> None:
        key: str
        if principal:
            key = f"principal:{principal.org_id}:{principal.user_id}"
        else:
            client_host = request.client.host if request.client else "unknown"
            key = f"ip:{client_host}"

        allowed, remaining, retry_after = limiter.check(key)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        if not allowed:
            err = rate_limited(retry_after=retry_after)
            err.details["limit"] = limit
            raise err

    return _rate_limit_dep

