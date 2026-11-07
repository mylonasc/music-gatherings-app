"""Inbound rate limiting for provider services.

The same token-bucket limiter that guards outbound calls also gates inbound
traffic, so admin panels, tests, and future callers cannot bypass shared
capacity. Exceeded requests get a structured 429 envelope plus a standard
``Retry-After`` header.
"""

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from common.alimiter import AsyncLimiter, QueueFullError, QueueTimeoutError


class InboundRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,  # type: ignore[no-untyped-def]
        limiter: AsyncLimiter,
        *,
        paths: tuple[str, ...] = ("/v1/search", "/v1/fetch"),
    ) -> None:
        super().__init__(app)
        self._limiter = limiter
        self._paths = paths

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path not in self._paths:
            return await call_next(request)
        operation = "search" if request.url.path.endswith("/search") else "fetch"
        try:
            async with self._limiter.slot(operation):
                return await call_next(request)
        except (QueueFullError, QueueTimeoutError):
            return JSONResponse(
                status_code=429,
                content={
                    "error": {
                        "code": "throttled",
                        "message": "provider is busy; retry later",
                        "retryable": True,
                    }
                },
                headers={"Retry-After": "30"},
            )
