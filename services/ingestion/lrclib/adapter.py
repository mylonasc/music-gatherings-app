"""Read-only LRCLIB API for private, personal lyric libraries.

Plain lyrics and original timestamped LRC are distinct artifacts. No scraping,
publishing, YAML parsing, or arbitrary provider URLs.
"""

import os
import re
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from common.alimiter import AsyncLimiter
from common.cache import ResponseCache, cache_key
from common.client import LimitedHttpClient
from common.contracts import (
    CapabilityResponse,
    FetchedArtifact,
    FetchRequest,
    FetchResponse,
    SearchItem,
    SearchRequest,
    SearchResponse,
)
from common.errors import InvalidResponseError
from common.limits import LimiterConfig, OperationLimits

SERVICE_NAME = "ingestion-lrclib"
SERVICE_VERSION = "0.1.0"
API_BASE = "https://lrclib.net/api"
USER_AGENT = "MusicGatherings/0.1.0 (https://github.com/mylonasc/music-gatherings-app)"
ID_RE = re.compile(r"^[1-9][0-9]{0,17}$")
ATTRIBUTION = "Lyrics via LRCLIB (https://lrclib.net); rights remain with their owners."
RIGHTS_WARNING = "Local storage is disabled; this result is reference-only."


class LyricsRecord(BaseModel):
    model_config = ConfigDict(extra="ignore", strict=True)

    id: int = Field(gt=0, le=999_999_999_999_999_999)
    trackName: str = Field(max_length=1000)
    artistName: str = Field(max_length=1000)
    instrumental: bool = False
    plainLyrics: str | None = Field(default=None, max_length=500_000)
    syncedLyrics: str | None = Field(default=None, max_length=500_000)


def _record(value: Any) -> LyricsRecord:
    try:
        return LyricsRecord.model_validate(value)
    except ValidationError:
        # Diagnostics may contain full lyrics: don't expose them.
        raise InvalidResponseError("unexpected LRCLIB record") from None


def _json(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        raise InvalidResponseError("LRCLIB returned invalid JSON") from None


class LrclibAdapter:
    def __init__(
        self,
        *,
        allow_storage: bool = True,
        client: LimitedHttpClient | None = None,
        limiter: AsyncLimiter | None = None,
        cache: ResponseCache | None = None,
        requests_per_minute: int = 20,
        min_interval_seconds: float = 0.5,
    ) -> None:
        self._allow_storage = allow_storage
        self._limiter = limiter or AsyncLimiter(LimiterConfig(
            overall=OperationLimits(requests_per_minute, 60.0, burst=1),
            search=OperationLimits(6, 60.0, burst=1),
            fetch=OperationLimits(10, 60.0, burst=1),
            max_concurrency=1,
            min_interval_seconds=min_interval_seconds,
            max_wait_seconds=10.0,
        ))
        self._client = client or LimitedHttpClient(self._limiter, max_attempts=2)
        self._cache = cache or ResponseCache(ttl_seconds=300.0, max_entries=32)

    @property
    def limiter(self) -> AsyncLimiter:
        return self._limiter

    @property
    def http_client(self) -> LimitedHttpClient:
        return self._client

    def capabilities(self) -> CapabilityResponse:
        return CapabilityResponse(
            provider="lrclib", artifact_types=["lyrics"],
            allows_storage=self._allow_storage,
            storage_note=(
                "Plain lyrics and timestamped LRC for personal local use; "
                "API availability is not a public redistribution license."
                if self._allow_storage else RIGHTS_WARNING
            ),
            rate_limit_requests=self._limiter.config.overall.requests,
            rate_limit_period_seconds=60.0,
        )

    async def search(self, body: SearchRequest) -> SearchResponse:
        if body.artifact_types and "lyrics" not in body.artifact_types:
            return SearchResponse(provider="lrclib")
        key = cache_key("search", body.model_dump())
        result: SearchResponse = await self._cache.get_or_fetch(key, lambda: self._search(body))
        return result

    async def _search(self, body: SearchRequest) -> SearchResponse:
        response = await self._client.request(
            "search", "GET", f"{API_BASE}/search",
            params={"q": body.query}, headers={"User-Agent": USER_AGENT},
        )
        payload = _json(response)
        if not isinstance(payload, list):
            raise InvalidResponseError("expected LRCLIB search array")
        items: list[SearchItem] = []
        for value in payload[:20]:  # v1 has at most 20 results; no pagination.
            record = _record(value)
            available = not record.instrumental and bool(record.plainLyrics or record.syncedLyrics)
            warnings = ["Instrumental: no lyrics."] if record.instrumental else []
            if not self._allow_storage:
                warnings.append(RIGHTS_WARNING)
            items.append(SearchItem(
                provider="lrclib", external_id=str(record.id),
                title=record.trackName, artist=record.artistName,
                artifact_types=["lyrics"] if available else [],
                source_url=f"{API_BASE}/get/{record.id}",
                attribution=ATTRIBUTION, warnings=warnings,
            ))
            if len(items) >= body.limit:
                break
        return SearchResponse(provider="lrclib", items=items)

    async def fetch(self, body: FetchRequest) -> FetchResponse:
        if not ID_RE.fullmatch(body.external_id):
            raise InvalidResponseError("invalid LRCLIB record id")
        if body.artifact_types and "lyrics" not in body.artifact_types:
            raise InvalidResponseError("LRCLIB supports lyrics only")
        key = cache_key("fetch", body.model_dump())
        result: FetchResponse = await self._cache.get_or_fetch(key, lambda: self._fetch(body))
        return result

    async def _fetch(self, body: FetchRequest) -> FetchResponse:
        response = await self._client.request(
            "fetch", "GET", f"{API_BASE}/get/{body.external_id}",
            headers={"User-Agent": USER_AGENT},
        )
        record = _record(_json(response))
        if str(record.id) != body.external_id:
            raise InvalidResponseError("LRCLIB returned a different record id")
        warnings: list[str] = []
        artifacts: list[FetchedArtifact] = []
        if record.instrumental:
            warnings.append("Instrumental: no lyrics.")
        else:
            for text, mime in (
                (record.plainLyrics, "text/plain"),
                (record.syncedLyrics, "application/x-lrc"),
            ):
                if text and text.strip():
                    artifacts.append(FetchedArtifact(
                        artifact_type="lyrics", mime_type=mime,
                        content_text=text if self._allow_storage else None,
                        attribution=ATTRIBUTION, storage_allowed=self._allow_storage,
                    ))
            if not artifacts:
                warnings.append("No plain or LRC lyrics available for this record.")
        if not self._allow_storage:
            warnings.append(RIGHTS_WARNING)
        return FetchResponse(
            provider="lrclib", external_id=str(record.id),
            title=record.trackName, artist=record.artistName,
            source_url=f"{API_BASE}/get/{record.id}", artifacts=artifacts, warnings=warnings,
        )


def adapter_from_env() -> LrclibAdapter:
    requests = int(os.environ.get("LRCLIB_REQUESTS_PER_MINUTE", "20"))
    interval = float(os.environ.get("LRCLIB_MIN_INTERVAL_SECONDS", "0.5"))
    if requests <= 0 or not 0.2 <= interval <= 60:
        raise ValueError("invalid LRCLIB rate configuration")
    return LrclibAdapter(
        allow_storage=os.environ.get("LRCLIB_ALLOW_STORAGE", "true").lower() == "true",
        requests_per_minute=requests, min_interval_seconds=interval,
    )
