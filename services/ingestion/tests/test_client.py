"""LimitedHttpClient tests: 429/cooldown, retries, backoff bounds, error mapping."""

import asyncio

import httpx
import pytest

from common.alimiter import AsyncLimiter
from common.client import LimitedHttpClient
from common.errors import (
    ForbiddenError,
    InvalidResponseError,
    NotFoundError,
    UpstreamError,
    parse_retry_after,
)
from common.limits import LimiterConfig, OperationLimits


class FakeClock:
    def __init__(self) -> None:
        self.now = 2000.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += max(0.0, seconds)
        await asyncio.sleep(0)


def permissive_limiter(clock: FakeClock, **overrides):  # type: ignore[no-untyped-def]
    config = LimiterConfig(
        overall=OperationLimits(1000, 60.0, burst=1000),
        search=OperationLimits(1000, 60.0, burst=1000),
        fetch=OperationLimits(1000, 60.0, burst=1000),
        **overrides,
    )
    return AsyncLimiter(config, clock=clock.clock, sleep=clock.sleep)


def mock_client(handler):  # type: ignore[no-untyped-def]
    def handle(request: httpx.Request) -> httpx.Response:
        return handler(request)

    return httpx.AsyncClient(transport=httpx.MockTransport(handle))


def test_retry_after_then_success_uses_single_cooldown() -> None:
    clock = FakeClock()
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if len(calls) == 1:
            return httpx.Response(429, headers={"retry-after": "5"}, json={})
        return httpx.Response(200, json={"ok": True})

    async def run():  # type: ignore[no-untyped-def]
        limiter = permissive_limiter(clock)
        client = LimitedHttpClient(
            limiter,
            client=mock_client(handler),
            backoff_base_seconds=0.0,
            sleep=clock.sleep,
        )
        response = await client.request("search", "GET", "https://provider.test/search")
        assert response.status_code == 200
        assert client.attempt_count == 2
        assert limiter.stats().throttled_attempts == 1
        return limiter

    limiter = asyncio.run(run())
    assert len(calls) == 2
    # Cooldown sleep (5s) happened inside the limiter; backoff base is 0.
    assert any(s >= 5.0 for s in clock.slept)
    assert limiter.stats().total_attempts == 2


def test_retry_after_http_date_parsing() -> None:
    retry = parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT", now=1445412480.0)
    assert retry == 0.0  # date is in the past relative to `now`
    retry = parse_retry_after("Wed, 21 Oct 2035 07:28:00 GMT", now=1445412480.0, cap=300.0)
    assert retry == 300.0  # far future is capped
    assert parse_retry_after(None) == 30.0
    assert parse_retry_after("garbage") == 30.0
    assert parse_retry_after("2.5") == 2.5


def test_retryable_5xx_eventually_succeeds() -> None:
    clock = FakeClock()
    attempts: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) < 3:
            return httpx.Response(503, json={})
        return httpx.Response(200, json={"ok": True})

    async def run() -> int:
        limiter = permissive_limiter(clock)
        client = LimitedHttpClient(
            limiter, client=mock_client(handler), backoff_base_seconds=0.0, sleep=clock.sleep
        )
        response = await client.request("fetch", "GET", "https://provider.test/fetch")
        assert response.status_code == 200
        return client.attempt_count

    assert asyncio.run(run()) == 3


def test_non_retryable_errors_raise_immediately() -> None:
    clock = FakeClock()

    async def run() -> None:
        limiter = permissive_limiter(clock)
        cases = [(404, NotFoundError), (403, ForbiddenError), (418, InvalidResponseError)]
        for status, exc in cases:
            def handler(_request: httpx.Request, status: int = status) -> httpx.Response:
                return httpx.Response(status, json={})

            client = LimitedHttpClient(limiter, client=mock_client(handler), sleep=clock.sleep)
            with pytest.raises(exc):
                await client.request("search", "GET", "https://provider.test/x")
            assert client.attempt_count == 1
            client._attempt_count = 0

    asyncio.run(run())


def test_streamed_responses_are_bounded_and_closed() -> None:
    class Body(httpx.AsyncByteStream):
        closed = False

        async def __aiter__(self):
            yield b"x" * 65536
            yield b"y" * 65536
            raise AssertionError("must stop before reading the rest")

        async def aclose(self):
            self.closed = True

    body = Body()

    async def run():
        clock = FakeClock()
        client = LimitedHttpClient(
            permissive_limiter(clock), max_response_bytes=70000,
            client=mock_client(lambda _: httpx.Response(200, stream=body)),
        )
        with pytest.raises(InvalidResponseError, match="size limit"):
            await client.request("fetch", "GET", "https://provider.test/x")
        assert client.attempt_count == 1

    asyncio.run(run())
    assert body.closed


def test_queued_request_honors_new_cooldown() -> None:
    clock = FakeClock()
    limiter = permissive_limiter(clock, max_wait_seconds=120)
    first_started = asyncio.Event()
    second_queued = asyncio.Event()
    starts = []

    async def handle(request):
        starts.append(clock.now)
        if len(starts) == 1:
            first_started.set()
            await second_queued.wait()
            return httpx.Response(429, headers={"retry-after": "10"})
        return httpx.Response(200, json={"ok": True})

    async def run():
        client = LimitedHttpClient(
            limiter, client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
            max_attempts=1, backoff_base_seconds=0, sleep=clock.sleep,
        )

        async def second():
            second_queued.set()
            return await client.request("fetch", "GET", "https://provider.test/second")

        first = asyncio.create_task(client.request("search", "GET", "https://provider.test/first"))
        await first_started.wait()
        waiter = asyncio.create_task(second())
        results = await asyncio.gather(first, waiter, return_exceptions=True)
        assert results[1].status_code == 200
        assert starts[1] - starts[0] >= 10

    asyncio.run(run())


def test_long_retry_after_is_not_shortened() -> None:
    from common.alimiter import QueueTimeoutError

    clock = FakeClock()
    limiter = permissive_limiter(clock, max_wait_seconds=1)
    calls = []

    def handle(request):
        calls.append(request)
        return httpx.Response(429, headers={"retry-after": "600"})

    async def run():
        client = LimitedHttpClient(
            limiter, client=mock_client(handle), sleep=clock.sleep, backoff_base_seconds=0,
        )
        with pytest.raises(QueueTimeoutError):
            await client.request("fetch", "GET", "https://provider.test/x")

    asyncio.run(run())
    assert len(calls) == 1
    assert limiter.stats().cooldown_remaining >= 600


def test_attempts_are_bounded() -> None:
    clock = FakeClock()

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={})

    async def run() -> LimitedHttpClient:
        limiter = permissive_limiter(clock)
        client = LimitedHttpClient(
            limiter,
            client=mock_client(handler),
            max_attempts=3,
            backoff_base_seconds=0.0,
            sleep=clock.sleep,
        )
        with pytest.raises(UpstreamError):
            await client.request("fetch", "GET", "https://provider.test/x")
        return client

    client = asyncio.run(run())
    assert client.attempt_count == 3


def test_backoff_is_capped_with_jitter_bounds() -> None:
    clock = FakeClock()
    limiter = permissive_limiter(clock)
    client = LimitedHttpClient(limiter, backoff_base_seconds=4.0, backoff_cap_seconds=10.0)
    assert 4.0 <= client.backoff_for_attempt(0) <= 5.0
    assert 8.0 <= client.backoff_for_attempt(1) <= 9.0
    assert 10.0 <= client.backoff_for_attempt(5) <= 11.0


def test_connect_errors_are_retryable_then_fail() -> None:
    clock = FakeClock()

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused")

    async def run() -> None:
        limiter = permissive_limiter(clock)
        client = LimitedHttpClient(
            limiter,
            client=mock_client(handler),
            max_attempts=2,
            backoff_base_seconds=0.0,
            sleep=clock.sleep,
        )
        with pytest.raises(UpstreamError):
            await client.request("search", "GET", "https://provider.test/x")
        assert client.attempt_count == 2

    asyncio.run(run())
