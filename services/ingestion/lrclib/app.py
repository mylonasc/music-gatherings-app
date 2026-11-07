"""Private LRCLIB search and lyrics service."""

from common.contracts import (
    CapabilityResponse,
    FetchRequest,
    FetchResponse,
    SearchRequest,
    SearchResponse,
    StatsResponse,
)
from common.service import create_provider_app
from lrclib.adapter import SERVICE_NAME, SERVICE_VERSION, adapter_from_env

_adapter = adapter_from_env()


async def _search(body: SearchRequest) -> SearchResponse:
    return await _adapter.search(body)


async def _fetch(body: FetchRequest) -> FetchResponse:
    return await _adapter.fetch(body)


async def _stats() -> StatsResponse:
    return StatsResponse(
        provider="lrclib",
        limiter=_adapter.limiter.snapshot(),
        upstream_requests=_adapter.http_client.attempt_count,
        throttled_requests=_adapter.limiter.stats().throttled_attempts,
    )


def _capabilities() -> CapabilityResponse:
    return _adapter.capabilities()


app = create_provider_app(
    service_name=SERVICE_NAME,
    version=SERVICE_VERSION,
    capabilities=_capabilities,
    search=_search,
    fetch=_fetch,
    stats=_stats,
)
