"""Genius adapter: official developer API only (search + song metadata).

No `lyricsgenius` dependency and no page scraping: the official API does not
serve lyric text, and scraping lyrics violates Genius' ToS. `fetch` therefore
returns reference-only results (metadata + song page URL, nothing storable).
"""

import os
import re
from typing import Any

import httpx

from common.alimiter import AsyncLimiter
from common.cache import ResponseCache, cache_key
from common.client import LimitedHttpClient
from common.contracts import (
    CapabilityResponse,
    FetchRequest,
    FetchResponse,
    SearchItem,
    SearchRequest,
    SearchResponse,
)
from common.errors import InvalidResponseError, NotConfiguredError
from common.limits import LimiterConfig

SERVICE_NAME = "ingestion-genius"
SERVICE_VERSION = "0.1.0"
GENIUS_API_BASE = "https://api.genius.com"
MAX_RESPONSE_BYTES = 1_000_000
SONG_ID_RE = re.compile(r"^[0-9]{1,12}$")
REFERENCE_WARNING = (
    "Genius lyrics require publisher licensing and are not served by the API; "
    "this result is reference-only (metadata + song page link)."
)


class GeniusAdapter:
    def __init__(
        self,
        token: str | None,
        *,
        client: LimitedHttpClient | None = None,
        limiter: AsyncLimiter | None = None,
        cache: ResponseCache | None = None,
        upstream_requests: dict[str, int] | None = None,
    ) -> None:
        self._token = token
        self._limiter = limiter or AsyncLimiter(LimiterConfig())
        self._client = client or LimitedHttpClient(self._limiter)
        self._cache = cache or ResponseCache(ttl_seconds=300.0)
        self._upstream_requests = upstream_requests if upstream_requests is not None else {"n": 0}

    @property
    def configured(self) -> bool:
        return bool(self._token)

    @property
    def limiter(self) -> AsyncLimiter:
        return self._limiter

    @property
    def http_client(self) -> LimitedHttpClient:
        return self._client

    def capabilities(self) -> CapabilityResponse:
        return CapabilityResponse(
            provider="genius",
            artifact_types=[],
            supports_search=self.configured,
            supports_fetch=self.configured,
            allows_storage=False,
            storage_note=(
                "Reference-only: the Genius API serves metadata, not lyric text, "
                "and scraping lyrics violates Genius' ToS."
            ),
            rate_limit_requests=20,
            rate_limit_period_seconds=60.0,
        )

    def _require_token(self) -> str:
        if not self._token:
            raise NotConfiguredError("GENIUS_ACCESS_TOKEN is not set")
        return self._token

    async def search(self, body: SearchRequest) -> SearchResponse:
        token = self._require_token()
        key = cache_key("search", {"provider": "genius", **body.model_dump()})
        result: SearchResponse = await self._cache.get_or_fetch(
            key, lambda: self._do_search(token, body)
        )
        return result

    async def _do_search(self, token: str, body: SearchRequest) -> SearchResponse:
        response = await self._client.request(
            "search",
            "GET",
            f"{GENIUS_API_BASE}/search",
            params={"q": body.query},
            headers={"Authorization": f"Bearer {token}"},
        )
        payload = _bounded_json(response)
        items: list[SearchItem] = []
        for hit in payload.get("response", {}).get("hits", []):
            result = hit.get("result", {}) if isinstance(hit, dict) else {}
            if hit.get("type") != "song" or not isinstance(result, dict):
                continue
            try:
                raw_id = result.get("id")
                if raw_id is None:
                    continue
                song_id = int(raw_id)
            except (TypeError, ValueError):
                continue
            artist = result.get("primary_artist") or {}
            items.append(
                SearchItem(
                    provider="genius",
                    external_id=str(song_id),
                    title=result.get("title"),
                    artist=artist.get("name") if isinstance(artist, dict) else None,
                    artifact_types=[],
                    source_url=result.get("url"),
                    attribution="Metadata by Genius (https://genius.com)",
                    warnings=[REFERENCE_WARNING],
                )
            )
            if len(items) >= body.limit:
                break
        return SearchResponse(items=items, provider="genius")

    async def fetch(self, body: FetchRequest) -> FetchResponse:
        token = self._require_token()
        if not SONG_ID_RE.fullmatch(body.external_id):
            raise InvalidResponseError("invalid Genius song id")
        key = cache_key("fetch", {"provider": "genius", **body.model_dump()})
        result: FetchResponse = await self._cache.get_or_fetch(
            key, lambda: self._do_fetch(token, body)
        )
        return result

    async def _do_fetch(self, token: str, body: FetchRequest) -> FetchResponse:
        response = await self._client.request(
            "fetch",
            "GET",
            f"{GENIUS_API_BASE}/songs/{body.external_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        payload = _bounded_json(response)
        song = payload.get("response", {}).get("song", {})
        if not isinstance(song, dict):
            raise InvalidResponseError("unexpected Genius song payload")
        artist = song.get("primary_artist") or {}
        return FetchResponse(
            provider="genius",
            external_id=body.external_id,
            title=song.get("title"),
            artist=artist.get("name") if isinstance(artist, dict) else None,
            source_url=song.get("url"),
            artifacts=[],
            warnings=[REFERENCE_WARNING],
        )


def _bounded_json(response: httpx.Response) -> dict[str, Any]:
    if len(response.content) > MAX_RESPONSE_BYTES:
        raise InvalidResponseError("provider response too large")
    try:
        payload = response.json()
    except ValueError as exc:
        raise InvalidResponseError("provider returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise InvalidResponseError("unexpected provider payload")
    return payload


def adapter_from_env(
    *,
    client: LimitedHttpClient | None = None,
    limiter: AsyncLimiter | None = None,
    cache: ResponseCache | None = None,
) -> GeniusAdapter:
    return GeniusAdapter(
        os.environ.get("GENIUS_ACCESS_TOKEN"),
        client=client,
        limiter=limiter,
        cache=cache,
    )
