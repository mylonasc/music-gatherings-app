"""Genius adapter tests: fixture-based mapping, SSRF guards, secret hygiene."""

import asyncio
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from common.alimiter import AsyncLimiter
from common.client import LimitedHttpClient
from common.contracts import FetchRequest, SearchRequest
from common.errors import InvalidResponseError, NotConfiguredError, ProviderError
from common.limits import LimiterConfig, OperationLimits
from genius.adapter import GeniusAdapter

SEARCH_FIXTURE = {
    "response": {
        "hits": [
            {
                "type": "song",
                "result": {
                    "id": 111,
                    "title": "Blue Test",
                    "primary_artist": {"name": "Tester"},
                    "url": "https://genius.com/Tester-blue-test-lyrics",
                },
            },
            {"type": "song", "result": {"id": "not-an-int"}},
            {"type": "video", "result": {"id": 999}},
        ]
    }
}

SONG_FIXTURE = {
    "response": {
        "song": {
            "title": "Blue Test",
            "primary_artist": {"name": "Tester"},
            "url": "https://genius.com/Tester-blue-test-lyrics",
        }
    }
}


class FakeClock:
    def __init__(self) -> None:
        self.now = 5000.0

    def clock(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += max(0.0, seconds)
        await asyncio.sleep(0)


def permissive_limiter(clock: FakeClock) -> AsyncLimiter:
    config = LimiterConfig(
        overall=OperationLimits(1000, 60.0, burst=1000),
        search=OperationLimits(1000, 60.0, burst=1000),
        fetch=OperationLimits(1000, 60.0, burst=1000),
    )
    return AsyncLimiter(config, clock=clock.clock, sleep=clock.sleep)


def mock_client(clock: FakeClock, handler, token_holder: dict):  # type: ignore[no-untyped-def]
    def handle(request: httpx.Request) -> httpx.Response:
        token_holder["auth"] = request.headers.get("authorization")
        token_holder["url"] = str(request.url)
        return handler(request)

    transport = httpx.MockTransport(handle)
    limiter = permissive_limiter(clock)
    client = LimitedHttpClient(
        limiter,
        client=httpx.AsyncClient(transport=transport),
        backoff_base_seconds=0.0,
        sleep=clock.sleep,
    )
    return client


def test_search_maps_official_api_metadata() -> None:
    clock = FakeClock()
    seen: dict = {}
    client = mock_client(
        clock, lambda _r: httpx.Response(200, json=SEARCH_FIXTURE), seen
    )
    adapter = GeniusAdapter("SECRET-TOKEN", client=client)

    async def run():  # type: ignore[no-untyped-def]
        return await adapter.search(SearchRequest(query="blue"))

    response = asyncio.run(run())
    assert len(response.items) == 1  # malformed/non-song hits skipped
    item = response.items[0]
    assert (item.external_id, item.title, item.artist) == ("111", "Blue Test", "Tester")
    assert item.source_url == "https://genius.com/Tester-blue-test-lyrics"
    assert item.artifact_types == []
    assert any("reference-only" in w for w in item.warnings)
    # Bearer token used, and only the official API host contacted.
    assert seen["auth"] == "Bearer SECRET-TOKEN"
    assert seen["url"].startswith("https://api.genius.com/search")


def test_fetch_is_reference_only() -> None:
    clock = FakeClock()
    seen: dict = {}
    client = mock_client(clock, lambda _r: httpx.Response(200, json=SONG_FIXTURE), seen)
    adapter = GeniusAdapter("SECRET-TOKEN", client=client)

    async def run():  # type: ignore[no-untyped-def]
        return await adapter.fetch(FetchRequest(external_id="111"))

    fetched = asyncio.run(run())
    assert fetched.title == "Blue Test"
    assert fetched.artifacts == []
    assert any("reference-only" in w for w in fetched.warnings)
    assert seen["url"] == "https://api.genius.com/songs/111"


def test_unconfigured_adapter_returns_structured_503() -> None:


    adapter = GeniusAdapter(None)
    assert adapter.configured is False
    caps = adapter.capabilities()
    assert caps.supports_search is False

    async def run():  # type: ignore[no-untyped-def]
        with pytest.raises(NotConfiguredError):
            await adapter.search(SearchRequest(query="blue"))

    asyncio.run(run())
    # Service-level envelope (fresh app module state is configured via env;
    # here we only assert the envelope shape for the error path).
    assert NotConfiguredError("x").to_envelope() == {
        "error": {"code": "not_configured", "message": "x", "retryable": False}
    }


def test_invalid_song_ids_rejected_before_any_http() -> None:
    clock = FakeClock()
    calls: list = []
    client = mock_client(clock, lambda r: calls.append(r) or httpx.Response(200, json={}), {})
    adapter = GeniusAdapter("SECRET-TOKEN", client=client)

    async def run() -> None:
        for bad in ("abc", "../songs/1", "1 OR 1=1", "https://evil.test/x"):
            with pytest.raises(ProviderError):
                await adapter.fetch(FetchRequest(external_id=bad))

    asyncio.run(run())
    assert calls == []
    assert client.attempt_count == 0


def test_redirects_are_errors_not_followed() -> None:
    clock = FakeClock()
    seen: dict = {}
    client = mock_client(
        clock, lambda _r: httpx.Response(302, headers={"location": "https://evil.test/"}), seen
    )
    adapter = GeniusAdapter("SECRET-TOKEN", client=client)

    async def run() -> None:
        with pytest.raises(InvalidResponseError, match="redirect"):
            await adapter.search(SearchRequest(query="blue"))

    asyncio.run(run())


def test_secrets_never_leak_into_errors() -> None:
    clock = FakeClock()
    seen: dict = {}
    client = mock_client(clock, lambda _r: httpx.Response(500, json={}), seen)
    adapter = GeniusAdapter("SUPER-SECRET-TOKEN", client=client)

    async def run() -> ProviderError | None:
        try:
            await adapter.search(SearchRequest(query="blue"))
        except ProviderError as exc:
            return exc
        return None

    error = asyncio.run(run())
    assert error is not None
    assert "SUPER-SECRET-TOKEN" not in str(error)
    assert "SUPER-SECRET-TOKEN" not in str(error.to_envelope())


def test_genius_service_endpoints_use_envelope() -> None:
    import os
    from unittest import mock

    from fastapi.testclient import TestClient

    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("GENIUS_ACCESS_TOKEN", None)
        import importlib

        import genius.app as genius_app

        importlib.reload(genius_app)
        client = TestClient(genius_app.app)
        assert client.get("/health").status_code == 200
        caps = client.get("/v1/capabilities").json()
        assert caps["provider"] == "genius"
        assert caps["supports_search"] is False
        search = client.post("/v1/search", json={"query": "blue"})
        assert search.status_code == 503
        assert search.json()["error"]["code"] == "not_configured"
