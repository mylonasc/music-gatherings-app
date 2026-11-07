"""Inbound gate tests: providers answer 429 (with Retry-After) when saturated."""

import asyncio

from fastapi.testclient import TestClient

from common.alimiter import AsyncLimiter
from common.contracts import SearchRequest
from common.limits import LimiterConfig, OperationLimits
from common.service import create_provider_app
from common.contracts import (
    CapabilityResponse,
    FetchRequest,
    FetchResponse,
    SearchResponse,
    StatsResponse,
)


def make_app(max_wait_seconds: float = 0.0):  # type: ignore[no-untyped-def]
    tight = LimiterConfig(
        overall=OperationLimits(1, 3600.0, burst=1),
        search=OperationLimits(1, 3600.0, burst=1),
        fetch=OperationLimits(1, 3600.0, burst=1),
        max_wait_seconds=max_wait_seconds,
    )
    limiter = AsyncLimiter(tight)

    async def search(body: SearchRequest) -> SearchResponse:
        return SearchResponse(items=[], provider="t")

    async def fetch(body: FetchRequest) -> FetchResponse:
        return FetchResponse(provider="t", external_id=body.external_id)

    async def stats() -> StatsResponse:
        return StatsResponse(provider="t")

    return create_provider_app(
        service_name="t",
        version="0.0.0",
        capabilities=lambda: CapabilityResponse(provider="t", artifact_types=[]),
        search=search,
        fetch=fetch,
        stats=stats,
        limiter=limiter,
    ), limiter


def test_inbound_gate_returns_429_with_retry_after() -> None:
    app, limiter = make_app()
    client = TestClient(app)
    assert client.post("/v1/search", json={"query": "x", "limit": 1}).status_code == 200
    limited = client.post("/v1/search", json={"query": "x", "limit": 1})
    assert limited.status_code == 429
    assert limited.headers["retry-after"] == "30"
    assert limited.json()["error"]["code"] == "throttled"
    assert limiter.stats().total_attempts == 1


def test_health_and_capabilities_are_not_gated() -> None:
    app, _limiter = make_app()
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/v1/capabilities").status_code == 200
