"""Ultimate Guitar provider service: contract-conformant but disabled."""

from common.contracts import StatsResponse
from common.service import create_provider_app
from ultimateguitar.adapter import (
    SERVICE_NAME,
    SERVICE_VERSION,
    capabilities,
    fetch,
    search,
)


async def _stats() -> StatsResponse:
    return StatsResponse(provider="ultimate_guitar")


app = create_provider_app(
    service_name=SERVICE_NAME,
    version=SERVICE_VERSION,
    capabilities=capabilities,
    search=search,
    fetch=fetch,
    stats=_stats,
)
