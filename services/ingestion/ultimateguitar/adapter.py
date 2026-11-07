"""Ultimate Guitar adapter: explicitly disabled (documented product limitation).

There is no public Ultimate Guitar API, and scraping tabs would violate
their ToS and the publisher rights behind the content (see PROVIDERS.md).
This service implements the v1 contract so orchestration treats it
uniformly, but search/fetch always return structured 503 errors.
"""

from common.contracts import (
    CapabilityResponse,
    FetchRequest,
    FetchResponse,
    SearchRequest,
    SearchResponse,
)
from common.errors import ProviderUnavailableError

SERVICE_NAME = "ingestion-ultimate-guitar"
SERVICE_VERSION = "0.1.0"

UNAVAILABLE_MESSAGE = (
    "Ultimate Guitar offers no public API, and scraping tabs would violate "
    "their terms and publisher rights. See services/ingestion/PROVIDERS.md. "
    "This integration stays disabled until a licensed API exists."
)


def capabilities() -> CapabilityResponse:
    return CapabilityResponse(
        provider="ultimate_guitar",
        artifact_types=[],
        supports_search=False,
        supports_fetch=False,
        allows_storage=False,
        storage_note=UNAVAILABLE_MESSAGE,
    )


async def search(body: SearchRequest) -> SearchResponse:
    raise ProviderUnavailableError(UNAVAILABLE_MESSAGE)


async def fetch(body: FetchRequest) -> FetchResponse:
    raise ProviderUnavailableError(UNAVAILABLE_MESSAGE)
