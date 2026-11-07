"""TTL response cache with in-flight request coalescing.

Identical concurrent requests share a single upstream call; completed search
responses are cached for ``ttl_seconds``. Cache keys include the operation
and the full canonical parameter set so different queries never collide.
"""

import asyncio
import hashlib
import json
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    coalesced: int = 0
    evictions: int = 0
    entries: int = 0


def cache_key(operation: str, params: dict[str, Any]) -> str:
    canonical = json.dumps(params, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{operation}:{digest}"


class ResponseCache:
    def __init__(
        self,
        *,
        ttl_seconds: float = 300.0,
        max_entries: int = 1000,
        clock: Any = None,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_entries = max(1, max_entries)
        self._clock = clock or time.monotonic
        self._entries: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._in_flight: dict[str, asyncio.Future] = {}
        self._lock = asyncio.Lock()
        self._stats = CacheStats()

    def stats(self) -> CacheStats:
        return CacheStats(
            hits=self._stats.hits,
            misses=self._stats.misses,
            coalesced=self._stats.coalesced,
            evictions=self._stats.evictions,
            entries=len(self._entries),
        )

    def get(self, key: str) -> Any | None:
        """Synchronous cache read (no lock needed for tests/introspection)."""
        stored = self._entries.get(key)
        if stored is None:
            return None
        expires_at, value = stored
        if self._clock() >= expires_at:
            self._entries.pop(key, None)
            return None
        self._entries.move_to_end(key)
        return value

    async def get_or_fetch(self, key: str, fetch: Any) -> Any:
        """Return the cached value or run ``fetch`` once per key.

        Concurrent callers with the same key await the single in-flight
        fetch instead of issuing duplicate upstream requests.
        """
        async with self._lock:
            stored = self._entries.get(key)
            if stored is not None:
                expires_at, value = stored
                if self._clock() < expires_at:
                    self._entries.move_to_end(key)
                    self._stats.hits += 1
                    return value
                self._entries.pop(key, None)
            ongoing = self._in_flight.get(key)
            if ongoing is None:
                waiter: asyncio.Future = asyncio.get_running_loop().create_future()
                self._in_flight[key] = waiter
                self._stats.misses += 1
            else:
                self._stats.coalesced += 1
        if ongoing is not None:
            return await ongoing
        try:
            value = await fetch()
        except Exception as exc:
            async with self._lock:
                self._in_flight.pop(key, None)
                if not waiter.done():
                    waiter.set_exception(exc)
            raise
        async with self._lock:
            self._entries[key] = (self._clock() + self._ttl, value)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)
                self._stats.evictions += 1
            self._in_flight.pop(key, None)
            if not waiter.done():
                waiter.set_result(value)
        return value

    def invalidate(self, key: str) -> None:
        self._entries.pop(key, None)
