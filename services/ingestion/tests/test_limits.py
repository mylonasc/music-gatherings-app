"""Fake-clock tests: quotas, bursts, spacing, concurrency, cooldowns, circuits."""

import asyncio

import pytest

from common.alimiter import AsyncLimiter, QueueFullError, QueueTimeoutError
from common.limits import LimiterConfig, OperationLimits


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0
        self.sleeps: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += max(0.0, seconds)
        await asyncio.sleep(0)


def make_limiter(clock: FakeClock, **overrides):  # type: ignore[no-untyped-def]
    config = LimiterConfig(**overrides)
    return AsyncLimiter(config, clock=clock.clock, sleep=clock.sleep)


def test_overall_quota_and_burst() -> None:
    clock = FakeClock()
    limiter = make_limiter(
        clock,
        overall=OperationLimits(2, 60.0, burst=2),
        search=OperationLimits(100, 60.0, burst=100),
        fetch=OperationLimits(100, 60.0, burst=100),
        max_wait_seconds=5.0,
    )

    async def run() -> None:
        async with limiter.slot("search"):
            pass
        async with limiter.slot("search"):
            pass
        with pytest.raises(QueueTimeoutError):
            async with limiter.slot("search"):
                pass

    asyncio.run(run())
    # Needed wait (30s for 2 req/60s) exceeds the 5s budget: fail without sleeping.
    assert clock.sleeps == []
    assert limiter.stats().total_attempts == 2


def test_quota_refills_after_period() -> None:
    clock = FakeClock()
    limiter = make_limiter(
        clock,
        overall=OperationLimits(2, 60.0, burst=2),
        search=OperationLimits(100, 60.0, burst=100),
        fetch=OperationLimits(100, 60.0, burst=100),
        max_wait_seconds=120.0,
    )

    async def run() -> None:
        async with limiter.slot("search"):
            pass
        async with limiter.slot("search"):
            pass
        async with limiter.slot("search"):
            pass

    asyncio.run(run())
    assert clock.sleeps == [30.0]
    assert limiter.stats().total_attempts == 3


def test_per_operation_quotas_apply_together() -> None:
    clock = FakeClock()
    limiter = make_limiter(
        clock,
        overall=OperationLimits(100, 60.0, burst=100),
        search=OperationLimits(1, 60.0, burst=1),
        fetch=OperationLimits(100, 60.0, burst=100),
        max_wait_seconds=1.0,
    )

    async def run() -> None:
        async with limiter.slot("search"):
            pass
        # Search quota exhausted while fetch still has capacity.
        with pytest.raises(QueueTimeoutError):
            async with limiter.slot("search"):
                pass
        async with limiter.slot("fetch"):
            pass

    asyncio.run(run())


def test_minimum_spacing_between_starts() -> None:
    clock = FakeClock()
    limiter = make_limiter(
        clock,
        overall=OperationLimits(100, 60.0, burst=100),
        search=OperationLimits(100, 60.0, burst=100),
        fetch=OperationLimits(100, 60.0, burst=100),
        min_interval_seconds=3.0,
    )
    starts: list[float] = []

    async def run() -> None:
        for _ in range(3):
            async with limiter.slot("search"):
                starts.append(clock.now)

    asyncio.run(run())
    assert starts[1] - starts[0] >= 3.0
    assert starts[2] - starts[1] >= 3.0


def test_max_concurrency_is_one_by_default() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock)
    assert limiter.config.max_concurrency == 1

    entered: list[str] = []
    release = asyncio.Event()

    async def holder() -> None:
        async with limiter.slot("search"):
            entered.append("holder")
            await release.wait()

    async def waiter() -> None:
        await asyncio.sleep(0)
        async with limiter.slot("search"):
            entered.append("waiter")

    async def run() -> None:
        first = asyncio.ensure_future(holder())
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        second = asyncio.ensure_future(waiter())
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert entered == ["holder"], f"concurrency violated: {entered}"
        release.set()
        await first
        await second
        assert entered == ["holder", "waiter"]

    asyncio.run(run())


def test_queue_bound_rejects_overflow() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock, max_waiters=0)
    with pytest.raises(QueueFullError):
        asyncio.run(_acquire(limiter))


async def _acquire(limiter: AsyncLimiter) -> None:
    async with limiter.slot("search"):
        pass


def test_retry_after_cooldown_blocks_all_operations() -> None:
    clock = FakeClock()
    limiter = make_limiter(clock, max_wait_seconds=120.0)
    limiter.report_throttled(10.0)

    async def run() -> None:
        async with limiter.slot("fetch"):
            pass

    asyncio.run(run())
    assert clock.now >= 1010.0
    assert limiter.stats().throttled_attempts == 1


def test_circuit_opens_after_repeated_failures_and_recovers() -> None:
    clock = FakeClock()
    limiter = make_limiter(
        clock,
        circuit_failure_threshold=2,
        circuit_break_seconds=30.0,
        max_wait_seconds=120.0,
    )
    limiter.report_failure()
    assert not limiter.stats().circuit_open
    limiter.report_failure()
    assert limiter.stats().circuit_open

    async def run() -> None:
        async with limiter.slot("search"):
            pass

    asyncio.run(run())
    assert clock.now >= 1030.0
    limiter.report_success()
    assert limiter.stats().consecutive_failures == 0
