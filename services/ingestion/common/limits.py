"""Token-bucket math and limiter configuration (clock-injectable).

Pure computation lives here so fake-clock tests can verify quota, burst,
spacing, and cooldown semantics without real waiting. Async/sync wrappers
in sibling modules share this core.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class OperationLimits:
    requests: int
    period_seconds: float
    burst: int = 1

    @property
    def refill_per_second(self) -> float:
        return self.requests / self.period_seconds


@dataclass(frozen=True)
class LimiterConfig:
    overall: OperationLimits = field(
        default_factory=lambda: OperationLimits(20, 60.0, burst=2)
    )
    search: OperationLimits = field(
        default_factory=lambda: OperationLimits(6, 60.0, burst=1)
    )
    fetch: OperationLimits = field(
        default_factory=lambda: OperationLimits(10, 60.0, burst=1)
    )
    max_concurrency: int = 1
    min_interval_seconds: float = 0.0
    max_wait_seconds: float = 60.0
    max_waiters: int = 100
    circuit_failure_threshold: int = 5
    circuit_break_seconds: float = 60.0
    cooldown_default_seconds: float = 30.0


class Bucket:
    """Single token bucket. ``take`` returns seconds to wait (0 when allowed)."""

    def __init__(self, limits: OperationLimits, *, start_full: bool = True) -> None:
        self._capacity = float(max(1, limits.burst))
        self._refill = limits.refill_per_second
        self._tokens = self._capacity if start_full else 0.0
        self._updated_at: float | None = None

    def take(self, now: float) -> float:
        if self._updated_at is None:
            self._updated_at = now
        else:
            elapsed = max(0.0, now - self._updated_at)
            self._tokens = min(self._capacity, self._tokens + elapsed * self._refill)
            self._updated_at = now
        if self._tokens >= 1.0:
            self._tokens -= 1.0
            return 0.0
        deficit = 1.0 - self._tokens
        return deficit / self._refill if self._refill > 0 else float("inf")
