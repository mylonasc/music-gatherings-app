"""LRCLIB fixtures only: no live upstream dependency in CI."""

import asyncio

import httpx
import pytest
from fastapi.testclient import TestClient

from common.alimiter import AsyncLimiter
from common.client import LimitedHttpClient
from common.contracts import FetchRequest, SearchRequest
from common.errors import InvalidResponseError, NotFoundError
from common.limits import LimiterConfig, OperationLimits
from lrclib.adapter import LrclibAdapter, adapter_from_env

RECORD = {
    "id": 111, "trackName": "Fixture Song", "artistName": "Fixture Artist",
    "instrumental": False, "plainLyrics": "Original fixture line\n<script>inert</script>\n",
    "syncedLyrics": "[00:01.00] Original fixture line\n",
}


def make_adapter(payload, *, status=200, allow_storage=True):
    seen = []

    def handle(request):
        seen.append(request)
        return httpx.Response(status, json=payload)

    quota = OperationLimits(1000, 60, burst=1000)
    limiter = AsyncLimiter(LimiterConfig(overall=quota, search=quota, fetch=quota))
    client = LimitedHttpClient(
        limiter, client=httpx.AsyncClient(transport=httpx.MockTransport(handle)),
        max_attempts=1,
    )
    return LrclibAdapter(client=client, limiter=limiter, allow_storage=allow_storage), seen


def test_search_maps_metadata_without_returning_lyrics_and_caches():
    adapter, seen = make_adapter([RECORD, {**RECORD, "id": 222}])

    async def run():
        body = SearchRequest(query="Fixture & Song", limit=1)
        result = await adapter.search(body)
        assert await adapter.search(body) == result
        return result

    result = asyncio.run(run())
    assert len(result.items) == 1
    item = result.items[0]
    assert (item.provider, item.external_id, item.title, item.artist) == (
        "lrclib", "111", "Fixture Song", "Fixture Artist",
    )
    assert item.artifact_types == ["lyrics"]
    assert item.source_url == "https://lrclib.net/api/get/111"
    assert "Original fixture" not in result.model_dump_json()
    assert len(seen) == 1
    assert seen[0].url.host == "lrclib.net"
    assert seen[0].url.params["q"] == "Fixture & Song"
    assert "MusicGatherings/" in seen[0].headers["user-agent"]
    assert "authorization" not in seen[0].headers


def test_fetch_preserves_plain_and_lrc_separately():
    adapter, seen = make_adapter(RECORD)

    async def run():
        body = FetchRequest(external_id="111", artifact_types=["lyrics"])
        result = await adapter.fetch(body)
        assert await adapter.fetch(body) == result
        return result

    fetched = asyncio.run(run())
    assert len(seen) == 1
    assert str(seen[0].url) == "https://lrclib.net/api/get/111"
    assert [a.mime_type for a in fetched.artifacts] == ["text/plain", "application/x-lrc"]
    assert [a.content_text for a in fetched.artifacts] == [
        RECORD["plainLyrics"], RECORD["syncedLyrics"],
    ]
    assert all(a.storage_allowed and a.attribution for a in fetched.artifacts)


@pytest.mark.parametrize("field", ["plainLyrics", "syncedLyrics"])
def test_single_available_format(field):
    adapter, _ = make_adapter({**RECORD, "plainLyrics": None, "syncedLyrics": None,
                               field: RECORD[field]})
    result = asyncio.run(adapter.fetch(FetchRequest(external_id="111")))
    assert len(result.artifacts) == 1
    assert result.artifacts[0].content_text == RECORD[field]


def test_reference_mode_omits_text_even_from_cached_fetch():
    adapter, _ = make_adapter(RECORD, allow_storage=False)
    result = asyncio.run(adapter.fetch(FetchRequest(external_id="111")))
    assert all(a.content_text is None and not a.storage_allowed for a in result.artifacts)
    assert "Original fixture" not in result.model_dump_json()
    assert not adapter.capabilities().allows_storage
    assert any("reference-only" in w for w in result.warnings)


@pytest.mark.parametrize("instrumental", [True, False])
def test_instrumental_and_missing_lyrics(instrumental):
    adapter, _ = make_adapter({
        **RECORD, "instrumental": instrumental, "plainLyrics": None, "syncedLyrics": None,
    })
    fetched = asyncio.run(adapter.fetch(FetchRequest(external_id="111")))
    assert fetched.artifacts == []
    assert fetched.warnings


@pytest.mark.parametrize("bad", ["../1", "https://evil.test/1", "1?x=2", "0", "-1", "01"])
def test_ids_cannot_be_urls_or_paths(bad):
    adapter, seen = make_adapter(RECORD)
    with pytest.raises(InvalidResponseError):
        asyncio.run(adapter.fetch(FetchRequest(external_id=bad)))
    assert not seen


@pytest.mark.parametrize("payload", [[], {}, {**RECORD, "id": 112}, {**RECORD, "id": True},
                                      {**RECORD, "plainLyrics": {"unsafe": "payload"}}])
def test_bad_fetch_payloads_are_sanitized(payload):
    adapter, _ = make_adapter(payload)
    with pytest.raises(InvalidResponseError) as error:
        asyncio.run(adapter.fetch(FetchRequest(external_id="111")))
    assert "Original fixture" not in str(error.value)


def test_empty_search_and_unsupported_formats():
    adapter, seen = make_adapter([])
    assert asyncio.run(adapter.search(SearchRequest(query="none"))).items == []
    assert asyncio.run(adapter.search(
        SearchRequest(query="none", artifact_types=["tablature"])
    )).items == []
    assert len(seen) == 1
    with pytest.raises(InvalidResponseError):
        asyncio.run(adapter.fetch(FetchRequest(external_id="111", artifact_types=["tablature"])))
    assert len(seen) == 1


def test_not_found_and_redirects_are_not_followed():
    adapter, _ = make_adapter({}, status=404)
    with pytest.raises(NotFoundError):
        asyncio.run(adapter.fetch(FetchRequest(external_id="111")))
    adapter, seen = make_adapter({}, status=302)
    with pytest.raises(InvalidResponseError, match="redirect"):
        asyncio.run(adapter.search(SearchRequest(query="song")))
    assert len(seen) == 1


def test_no_credentials_required_and_rate_configuration(monkeypatch):
    monkeypatch.setenv("LRCLIB_REQUESTS_PER_MINUTE", "12")
    monkeypatch.setenv("LRCLIB_MIN_INTERVAL_SECONDS", "0.4")
    monkeypatch.setenv("LRCLIB_ALLOW_STORAGE", "false")
    adapter = adapter_from_env()
    assert adapter.capabilities().supports_search
    assert adapter.limiter.config.overall.requests == 12
    assert adapter.limiter.config.min_interval_seconds == 0.4
    assert not adapter.capabilities().allows_storage


def test_service_contract(monkeypatch):
    import lrclib.app as service

    adapter, _ = make_adapter(RECORD)
    monkeypatch.setattr(service, "_adapter", adapter)
    with TestClient(service.app) as client:
        assert client.get("/health").json()["service"] == "ingestion-lrclib"
        assert client.get("/v1/capabilities").json()["artifact_types"] == ["lyrics"]
        response = client.post("/v1/fetch", json={"external_id": "111"})
        assert response.status_code == 200
        assert len(response.json()["artifacts"]) == 2
        assert client.get("/v1/stats").json()["upstream_requests"] == 1
        assert client.post("/v1/fetch", json={"external_id": "../1"}).status_code == 502
