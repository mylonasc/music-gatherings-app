"""Per-user quotas for shared provider capacity (S07 infra; wired in S10).

Bounded sliding-window counters keyed by (scope, user id). Single-process
scope like the login throttler: one API replica initially. Online search and
import endpoints (S10) must check these quotas before touching provider
capacity so one user cannot monopolize shared limits.
"""

import threading
import time
from collections.abc import Callable


class QuotaExceeded(Exception):
    pass


class UserQuotaTracker:
    def __init__(
        self,
        *,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._hits: dict[str, list[float]] = {}

    def check(
        self, *, scope: str, user_id: str, max_attempts: int, window_seconds: float
    ) -> None:
        """Record one use or raise QuotaExceeded (does not sleep; S10 surfaces 429)."""
        now = self._clock()
        key = f"{scope}:{user_id}"
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if now - t < window_seconds]
            if len(hits) >= max_attempts:
                self._hits[key] = hits
                raise QuotaExceeded(f"quota exceeded for {scope}")
            hits.append(now)
            self._hits[key] = hits

    def usage(self, *, scope: str, user_id: str, window_seconds: float) -> int:
        now = self._clock()
        with self._lock:
            return len(
                [t for t in self._hits.get(f"{scope}:{user_id}", []) if now - t < window_seconds]
            )
