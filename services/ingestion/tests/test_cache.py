"""ResponseCache tests: TTL expiry, eviction, and in-flight coalescing."""

import asyncio

import pytest

from common.cache import ResponseCache, cache_key


class FakeClock:
    def __init__(self) -> None:
        self.now = 3000.0

    def clock(self) -> float:
        return self.now


def test_cache_hit_avoids_refetch() -> None:
    clock = FakeClock()
    cache = ResponseCache(ttl_seconds=60.0, clock=clock.clock)
    calls = {"n": 0}

    async def fetch():  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return {"items": [1]}

    async def run():  # type: ignore[no-untyped-def]
        first = await cache.get_or_fetch("search:abc", fetch)
        second = await cache.get_or_fetch("search:abc", fetch)
        return first, second

    first, second = asyncio.run(run())
    assert first == second == {"items": [1]}
    assert calls["n"] == 1
    assert cache.stats().hits == 1
    assert cache.stats().misses == 1


def test_expired_entries_refetch() -> None:
    clock = FakeClock()
    cache = ResponseCache(ttl_seconds=10.0, clock=clock.clock)
    calls = {"n": 0}

    async def fetch():  # type: ignore[no-untyped-def]
        calls["n"] += 1
        return calls["n"]

    async def run():  # type: ignore[no-untyped-def]
        assert await cache.get_or_fetch("k", fetch) == 1
        clock.now += 11.0
        assert await cache.get_or_fetch("k", fetch) == 2

    asyncio.run(run())
    assert calls["n"] == 2


def test_concurrent_identical_requests_coalesce() -> None:
    clock = FakeClock()
    cache = ResponseCache(ttl_seconds=60.0, clock=clock.clock)
    calls = {"n": 0}
    release = asyncio.Event()

    async def fetch():  # type: ignore[no-untyped-def]
        calls["n"] += 1
        await release.wait()
        return "shared"

    async def run():  # type: ignore[no-untyped-def]
        tasks = [asyncio.ensure_future(cache.get_or_fetch("k", fetch)) for _ in range(5)]
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        release.set()
        return await asyncio.gather(*tasks)

    results = asyncio.run(run())
    assert results == ["shared"] * 5
    assert calls["n"] == 1
    assert cache.stats().coalesced == 4


def test_failed_fetch_is_not_cached() -> None:
    clock = FakeClock()
    cache = ResponseCache(ttl_seconds=60.0, clock=clock.clock)
    calls = {"n": 0}

    async def fetch():  # type: ignore[no-untyped-def]
        calls["n"] += 1
        raise RuntimeError("upstream exploded")

    async def run() -> None:
        with pytest.raises(RuntimeError):
            await cache.get_or_fetch("k", fetch)
        with pytest.raises(RuntimeError):
            await cache.get_or_fetch("k", fetch)

    asyncio.run(run())
    assert calls["n"] == 2
    assert cache.stats().hits == 0


def test_cache_keys_include_full_parameters() -> None:
    assert cache_key("search", {"q": "blue"}) != cache_key("search", {"q": "red"})
    assert cache_key("search", {"q": "blue"}) == cache_key("search", {"q": "blue"})
    assert cache_key("search", {"q": "blue"}) != cache_key("fetch", {"q": "blue"})


def test_oldest_entries_evict_first() -> None:
    clock = FakeClock()
    cache = ResponseCache(ttl_seconds=60.0, max_entries=2, clock=clock.clock)

    async def run() -> None:
        async def fetch(value: str):  # type: ignore[no-untyped-def]
            return value

        await cache.get_or_fetch("a", lambda: fetch("a"))
        await cache.get_or_fetch("b", lambda: fetch("b"))
        await cache.get_or_fetch("c", lambda: fetch("c"))

    asyncio.run(run())
    assert cache.get("a") is None
    assert cache.get("b") == "b"
    assert cache.stats().evictions == 1
