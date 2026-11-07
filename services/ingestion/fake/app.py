"""Deterministic fake provider for tests, admin panels, and Playwright (S12).

Implements the full ingestion v1 contract with fixed in-memory fixtures —
no network, no randomness. Request counters let tests prove caching and
coalescing (upstream hits stay at 1 for repeated/identical requests).
"""

from typing import cast

from fastapi import FastAPI, HTTPException, Request

from common.contracts import (
    ArtifactType,
    CapabilityResponse,
    FetchedArtifact,
    FetchRequest,
    FetchResponse,
    HealthResponse,
    SearchItem,
    SearchRequest,
    SearchResponse,
    StatsResponse,
)

SERVICE_VERSION = "0.1.0"

# Original placeholder content (not real songs) so fixtures are freely usable.
_FIXTURES = [
    {
        "external_id": "fake-song-1",
        "title": "Blue Test Train",
        "artist": "The Determinists",
        "lyrics": "Rolling down the test track line\nEvery assertion passes fine\n",
        "chords": "[C] Rolling [G] down the [Am] test track [F] line\n",
        "source_url": "https://example.local/fake-song-1",
    },
    {
        "external_id": "fake-song-2",
        "title": "Green Test Light",
        "artist": "The Determinists",
        "lyrics": "Green light glows on empty staging\nNo flaky tests are ever aging\n",
        "chords": "[G] Green [D] light glows [Em] on [C] staging\n",
        "source_url": "https://example.local/fake-song-2",
    },
    {
        "external_id": "fake-song-3",
        "title": "Quiet Rehearsal Room",
        "artist": "Solo Fixture",
        "lyrics": "A quiet room, a muted string\nThe setup plays the same refrain\n",
        "chords": "[Am] A quiet [F] room, a [C] muted [G] string\n",
        "source_url": "https://example.local/fake-song-3",
    },
]


def create_app() -> FastAPI:
    app = FastAPI(title="Fake Ingestion Provider", version=SERVICE_VERSION)
    app.state.search_count = 0
    app.state.fetch_count = 0

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(service="ingestion-fake", version=SERVICE_VERSION)

    @app.get("/v1/capabilities", response_model=CapabilityResponse)
    def capabilities() -> CapabilityResponse:
        return CapabilityResponse(
            provider="fake",
            artifact_types=["lyrics", "chord_chart"],
            supports_search=True,
            supports_fetch=True,
            allows_storage=True,
            storage_note="Fixture content is original and freely storable.",
            rate_limit_requests=20,
            rate_limit_period_seconds=60.0,
        )

    @app.post("/v1/search", response_model=SearchResponse)
    def search(body: SearchRequest, request: Request) -> SearchResponse:
        request.app.state.search_count += 1
        query = body.query.strip().lower()
        wanted = set(body.artifact_types) if body.artifact_types else {"lyrics", "chord_chart"}
        items: list[SearchItem] = []
        for fixture in _FIXTURES:
            haystack = f"{fixture['title']} {fixture['artist']}".lower()
            if query and query not in haystack:
                continue
            offered: list[ArtifactType] = [
                cast(ArtifactType, t) for t in ("lyrics", "chord_chart") if t in wanted
            ]
            if not offered:
                continue
            items.append(
                SearchItem(
                    provider="fake",
                    external_id=fixture["external_id"],
                    title=fixture["title"],
                    artist=fixture["artist"],
                    artifact_types=offered,
                    source_url=fixture["source_url"],
                    attribution="Fake provider fixture (public domain placeholder)",
                    confidence=0.99,
                )
            )
            if len(items) >= body.limit:
                break
        return SearchResponse(items=items, provider="fake")

    @app.post("/v1/fetch", response_model=FetchResponse)
    def fetch(body: FetchRequest, request: Request) -> FetchResponse:
        request.app.state.fetch_count += 1
        fixture = next(
            (f for f in _FIXTURES if f["external_id"] == body.external_id), None
        )
        if fixture is None:
            raise HTTPException(status_code=404, detail="unknown external_id")
        wanted = set(body.artifact_types) if body.artifact_types else {"lyrics", "chord_chart"}
        artifacts: list[FetchedArtifact] = []
        if "lyrics" in wanted:
            artifacts.append(
                FetchedArtifact(
                    artifact_type="lyrics",
                    mime_type="text/plain",
                    content_text=fixture["lyrics"],
                    attribution="Fake provider fixture (public domain placeholder)",
                    storage_allowed=True,
                )
            )
        if "chord_chart" in wanted:
            artifacts.append(
                FetchedArtifact(
                    artifact_type="chord_chart",
                    mime_type="text/plain",
                    content_text=fixture["chords"],
                    attribution="Fake provider fixture (public domain placeholder)",
                    storage_allowed=True,
                )
            )
        return FetchResponse(
            provider="fake",
            external_id=fixture["external_id"],
            title=fixture["title"],
            artist=fixture["artist"],
            source_url=fixture["source_url"],
            artifacts=artifacts,
        )

    @app.get("/v1/stats", response_model=StatsResponse)
    def stats(request: Request) -> StatsResponse:
        return StatsResponse(
            provider="fake",
            upstream_requests=request.app.state.search_count + request.app.state.fetch_count,
        )

    @app.post("/v1/_reset")
    def reset(request: Request) -> dict[str, bool]:
        """Test-only counter reset (never exposed outside test deployments)."""
        request.app.state.search_count = 0
        request.app.state.fetch_count = 0
        return {"ok": True}

    return app


app = create_app()
