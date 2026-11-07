"""Async per-service limiter: quotas, burst, spacing, concurrency, cooldown.

Covers *every* outbound HTTP attempt (including retries and redirects) because
all service traffic flows through one ``LimitedHttpClient`` holding this
limiter. Inject ``clock``/``sleep`` in tests for deterministic fake time.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from .limits import Bucket, LimiterConfig


class QueueFullError(Exception):
    pass


class QueueTimeoutError(Exception):
    pass


class CircuitOpenError(Exception):
    pass


@dataclass
class LimiterStats:
    in_flight: int
    waiters: int
    consecutive_failures: int
    circuit_open: bool
    cooldown_remaining: float
    total_attempts: int
    throttled_attempts: int


class AsyncLimiter:
    def __init__(
        self,
        config: LimiterConfig | None = None,
        *,
        clock: Callable[[], float] | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._config = config or LimiterConfig()
        self._clock = clock or time.monotonic
        self._sleep = sleep or asyncio.sleep
        self._overall = Bucket(self._config.overall)
        self._operations = {
            "search": Bucket(self._config.search),
            "fetch": Bucket(self._config.fetch),
        }
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max(1, self._config.max_concurrency))
        self._waiters = 0
        self._in_flight = 0
        self._last_start: float | None = None
        self._cooldown_until = 0.0
        self._circuit_until = 0.0
        self._consecutive_failures = 0
        self._total_attempts = 0
        self._throttled_attempts = 0

    @property
    def config(self) -> LimiterConfig:
        return self._config

    def operation_bucket(self, operation: str) -> Bucket:
        try:
            return self._operations[operation]
        except KeyError:
            raise ValueError(f"unknown operation: {operation}") from None

    @asynccontextmanager
    async def slot(self, operation: str):  # type: ignore[no-untyped-def]
        """Hold a concurrency slot after rate/cooldown/circuit checks pass."""
        bucket = self.operation_bucket(operation)
        if self._waiters >= self._config.max_waiters:
            raise QueueFullError("too many queued provider requests")
        self._waiters += 1
        acquired = False
        deadline = self._clock() + self._config.max_wait_seconds
        try:
            try:
                if not self._semaphore.locked():
                    await self._semaphore.acquire()
                else:
                    await asyncio.wait_for(
                        self._semaphore.acquire(), timeout=self._config.max_wait_seconds
                    )
            except TimeoutError:
                raise QueueTimeoutError("timed out waiting for provider concurrency") from None
            acquired = True
            await self._wait_turn(bucket, deadline)
        except BaseException:
            if acquired:
                self._semaphore.release()
            raise
        finally:
            self._waiters -= 1
        self._in_flight += 1
        self._total_attempts += 1
        try:
            yield
        finally:
            self._in_flight -= 1
            self._semaphore.release()

    async def _wait_turn(self, bucket: Bucket, deadline: float) -> None:
        while True:
            now = self._clock()
            async with self._lock:
                spacing = (
                    self._last_start + self._config.min_interval_seconds - now
                    if self._last_start is not None else 0.0
                )
                wait = max(
                    0.0, self._circuit_until - now, self._cooldown_until - now,
                    spacing, bucket.wait_seconds(now), self._overall.wait_seconds(now),
                )
                if now > deadline and self._config.max_wait_seconds > 0:
                    raise QueueTimeoutError("timed out waiting for provider capacity")
                if wait <= 0:
                    bucket.take(now)
                    self._overall.take(now)
                    self._last_start = now
                    return
            if now + wait > deadline:
                raise QueueTimeoutError("timed out waiting for provider capacity")
            await self._sleep(wait)

    def report_success(self) -> None:
        self._consecutive_failures = 0

    def report_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._config.circuit_failure_threshold:
            self._circuit_until = self._clock() + self._config.circuit_break_seconds

    def report_throttled(self, retry_after_seconds: float) -> None:
        self._throttled_attempts += 1
        cooldown = max(0.0, retry_after_seconds or self._config.cooldown_default_seconds)
        self._cooldown_until = max(self._cooldown_until, self._clock() + cooldown)

    def stats(self) -> LimiterStats:
        now = self._clock()
        return LimiterStats(
            in_flight=self._in_flight,
            waiters=self._waiters,
            consecutive_failures=self._consecutive_failures,
            circuit_open=now < self._circuit_until,
            cooldown_remaining=max(0.0, self._cooldown_until - now),
            total_attempts=self._total_attempts,
            throttled_attempts=self._throttled_attempts,
        )

    def snapshot(self) -> dict[str, Any]:
        stats = self.stats()
        return {
            "operations": sorted(self._operations),
            "max_concurrency": self._config.max_concurrency,
            "min_interval_seconds": self._config.min_interval_seconds,
            "in_flight": stats.in_flight,
            "waiters": stats.waiters,
            "circuit_open": stats.circuit_open,
            "cooldown_remaining": stats.cooldown_remaining,
            "total_attempts": stats.total_attempts,
            "throttled_attempts": stats.throttled_attempts,
        }
