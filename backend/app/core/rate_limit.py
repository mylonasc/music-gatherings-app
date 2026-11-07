"""In-memory sliding-window rate limiter for auth endpoints.

Single-process scope is sufficient for S03 (one API replica). Limits are
configured through settings; the limiter instance is created per application
so tests can use small windows.
"""

import threading
import time


class RateLimiter:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._hits: dict[str, list[float]] = {}

    def allow(self, key: str, *, max_attempts: int, window_seconds: int) -> bool:
        now = time.monotonic()
        with self._lock:
            hits = [t for t in self._hits.get(key, []) if now - t < window_seconds]
            if len(hits) >= max_attempts:
                self._hits[key] = hits
                return False
            hits.append(now)
            self._hits[key] = hits
            return True
