"""Consumer-stack tests: limited client + cache + coalescing vs the fake provider.

These prove the S07 acceptance core: every upstream attempt passes the
limiter, repeated calls hit the cache (fake counters stay at 1), concurrent
identical calls coalesce, and the fake honors the v1 contract schemas.
"""

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

from common.alimiter import AsyncLimiter
from common.cache import ResponseCache, cache_key
from common.client import LimitedHttpClient
from common.contracts import FetchResponse, SearchResponse
from common.limits import LimiterConfig, OperationLimits

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "fake"))
from app import create_app as create_fake_app  # noqa: E402


class FakeClock:
    def __init__(self) -> None:
        self.now = 4000.0

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += max(0.0, seconds)
        await asyncio.sleep(0)


def make_stack(clock: FakeClock, app):  # type: ignore[no-untyped-def]
    config = LimiterConfig(
        overall=OperationLimits(1000, 60.0, burst=1000),
        search=OperationLimits(1000, 60.0, burst=1000),
        fetch=OperationLimits(1000, 60.0, burst=1000),
    )
    limiter = AsyncLimiter(config, clock=clock.clock, sleep=clock.sleep)
    transport = httpx.ASGITransport(app=app)
    client = LimitedHttpClient(
        limiter,
        client=httpx.AsyncClient(transport=transport, base_url="https://fake.test"),
        backoff_base_seconds=0.0,
        sleep=clock.sleep,
    )
    cache = ResponseCache(ttl_seconds=300.0, clock=clock.clock)
    return limiter, client, cache


def search_payload(query: str) -> dict:
    return {"query": query, "artifact_types": ["lyrics"], "limit": 10}


def test_fake_search_contract_and_cache() -> None:
    clock = FakeClock()
    app = create_fake_app()
    limiter, client, cache = make_stack(clock, app)

    async def run():  # type: ignore[no-untyped-def]
        async def do_search():  # type: ignore[no-untyped-def]
            response = await client.request(
                "search", "POST", "/v1/search", json=search_payload("blue")
            )
            assert response.status_code == 200
            return SearchResponse.model_validate(response.json())

        key = cache_key("search", search_payload("blue"))
        first = await cache.get_or_fetch(key, do_search)
        second = await cache.get_or_fetch(key, do_search)
        assert first.items and second.items
        assert first.items[0].title == "Blue Test Train"
        assert client.attempt_count == 1
        assert app.state.search_count == 1

    asyncio.run(run())


def test_concurrent_searches_coalesce_to_one_upstream_call() -> None:
    clock = FakeClock()
    app = create_fake_app()
    limiter, client, cache = make_stack(clock, app)

    async def run():  # type: ignore[no-untyped-def]
        async def do_search():  # type: ignore[no-untyped-def]
            response = await client.request(
                "search", "POST", "/v1/search", json=search_payload("green")
            )
            return SearchResponse.model_validate(response.json())

        key = cache_key("search", search_payload("green"))
        results = await asyncio.gather(*[cache.get_or_fetch(key, do_search) for _ in range(5)])
        assert all(r.items[0].external_id == "fake-song-2" for r in results)
        assert app.state.search_count == 1
        assert cache.stats().coalesced == 4

    asyncio.run(run())


def test_fake_fetch_contract() -> None:
    clock = FakeClock()
    app = create_fake_app()
    limiter, client, cache = make_stack(clock, app)

    async def run():  # type: ignore[no-untyped-def]
        response = await client.request(
            "fetch", "POST", "/v1/fetch", json={"external_id": "fake-song-1"}
        )
        assert response.status_code == 200
        fetched = FetchResponse.model_validate(response.json())
        kinds = {a.artifact_type for a in fetched.artifacts}
        assert kinds == {"lyrics", "chord_chart"}
        assert all(a.storage_allowed for a in fetched.artifacts)
        assert fetched.title == "Blue Test Train"
        assert app.state.fetch_count == 1

    asyncio.run(run())


def test_fake_unknown_external_id_maps_to_404() -> None:
    from common.errors import NotFoundError

    clock = FakeClock()
    app = create_fake_app()
    limiter, client, cache = make_stack(clock, app)

    async def run() -> None:
        with pytest.raises(NotFoundError):
            await client.request(
                "fetch", "POST", "/v1/fetch", json={"external_id": "nope"}
            )

    asyncio.run(run())


def test_fake_health_and_capabilities() -> None:
    from fastapi.testclient import TestClient

    app = create_fake_app()
    client = TestClient(app)
    health = client.get("/health").json()
    assert health == {"status": "ok", "service": "ingestion-fake", "version": "0.1.0"}
    caps = client.get("/v1/capabilities").json()
    assert caps["provider"] == "fake"
    assert set(caps["artifact_types"]) == {"lyrics", "chord_chart"}
    assert caps["allows_storage"] is True
