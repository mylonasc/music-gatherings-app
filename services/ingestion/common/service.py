"""Shared FastAPI scaffold for provider adapters (v1 contract).

Gives every adapter identical health/capabilities/search/fetch/stats routes
with structured error envelopes, so orchestration treats real, fake, and
disabled providers uniformly.
"""

from collections.abc import Awaitable, Callable
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from common.alimiter import AsyncLimiter
from common.contracts import (
    CapabilityResponse,
    FetchRequest,
    FetchResponse,
    HealthResponse,
    SearchRequest,
    SearchResponse,
    StatsResponse,
)
from common.errors import ProviderError
from common.inbound import InboundRateLimitMiddleware
from common.limits import LimiterConfig


def _envelope_response(error: ProviderError, http_status: int) -> JSONResponse:
    return JSONResponse(status_code=http_status, content=error.to_envelope())


def _http_status_for(error: ProviderError) -> int:
    return {
        "throttled": 429,
        "not_found": 404,
        "forbidden": 403,
        "provider_unavailable": 503,
        "not_configured": 503,
    }.get(error.code, 502)


def create_provider_app(
    *,
    service_name: str,
    version: str,
    capabilities: CapabilityResponse | Callable[[], CapabilityResponse],
    search: Callable[[SearchRequest], Awaitable[SearchResponse]],
    fetch: Callable[[FetchRequest], Awaitable[FetchResponse]],
    stats: Callable[[], Awaitable[StatsResponse]],
    limiter: AsyncLimiter | None = None,
    inbound_limits: tuple[str, ...] = ("/v1/search", "/v1/fetch"),
) -> FastAPI:
    app = FastAPI(title=f"Ingestion provider: {service_name}", version=version)
    gate = limiter or AsyncLimiter(LimiterConfig())
    app.add_middleware(InboundRateLimitMiddleware, limiter=gate, paths=inbound_limits)

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(service=service_name, version=version)

    @app.get("/v1/capabilities", response_model=CapabilityResponse)
    def get_capabilities() -> CapabilityResponse:
        if callable(capabilities):
            resolved: CapabilityResponse = capabilities()
            return resolved
        return capabilities

    @app.post("/v1/search", response_model=SearchResponse)
    async def post_search(body: SearchRequest) -> SearchResponse:
        return await search(body)

    @app.post("/v1/fetch", response_model=FetchResponse)
    async def post_fetch(body: FetchRequest) -> FetchResponse:
        return await fetch(body)

    @app.get("/v1/stats", response_model=StatsResponse)
    async def get_stats() -> StatsResponse:
        return await stats()

    @app.exception_handler(ProviderError)
    async def provider_error_handler(_request: Any, exc: ProviderError) -> JSONResponse:
        return _envelope_response(exc, _http_status_for(exc))

    return app
