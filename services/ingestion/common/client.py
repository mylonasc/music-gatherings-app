"""Single choke point for outbound provider HTTP.

Every attempt (initial, retry, redirect follow-up) acquires a limiter slot
first, so configured quotas cover pagination, retries, and redirects alike.
Upstream 429s feed provider-wide cooldowns; 5xx/connect errors feed the
circuit breaker with capped exponential backoff and jitter.
"""

import asyncio
import random
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from .alimiter import AsyncLimiter
from .errors import (
    ForbiddenError,
    InvalidResponseError,
    NotFoundError,
    ProviderError,
    ThrottledError,
    UpstreamError,
    parse_retry_after,
)


class LimitedHttpClient:
    def __init__(
        self,
        limiter: AsyncLimiter,
        *,
        client: httpx.AsyncClient | None = None,
        max_attempts: int = 3,
        backoff_base_seconds: float = 1.0,
        backoff_cap_seconds: float = 30.0,
        timeout_seconds: float = 15.0,
        max_response_bytes: int = 2_000_000,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ) -> None:
        self._limiter = limiter
        self._client = client or httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=False)
        self._max_response_bytes = max_response_bytes
        self._max_attempts = max(1, max_attempts)
        self._backoff_base = backoff_base_seconds
        self._backoff_cap = backoff_cap_seconds
        self._sleep = sleep or asyncio.sleep
        self._attempt_count = 0

    @property
    def attempt_count(self) -> int:
        return self._attempt_count

    def backoff_for_attempt(self, attempt: int) -> float:
        capped = min(self._backoff_cap, self._backoff_base * (2**attempt))
        backoff: float = capped + random.uniform(0, min(capped, 1.0))
        return backoff

    async def request(self, operation: str, method: str, url: str, **kwargs: Any) -> httpx.Response:
        last_error: ProviderError | None = None
        for attempt in range(self._max_attempts):
            async with self._limiter.slot(operation):
                self._attempt_count += 1
                try:
                    response = await self._bounded_request(method, url, **kwargs)
                except (httpx.ConnectError, httpx.TimeoutException):
                    last_error = UpstreamError("provider unreachable")
                    self._limiter.report_failure()
                except httpx.HTTPError:
                    last_error = UpstreamError("provider HTTP request failed")
                    self._limiter.report_failure()
                else:
                    # Publish cooldown/circuit changes before releasing concurrency.
                    outcome = self._classify(response)
                    if outcome is None:
                        self._limiter.report_success()
                        return response
                    if isinstance(outcome, ThrottledError):
                        self._limiter.report_throttled(outcome.retry_after_seconds or 0)
                    else:
                        self._limiter.report_failure()
                    last_error = outcome
                    if not outcome.retryable:
                        raise outcome
            # Retryable: cooldown (429) or backoff already elapsed via limiter;
            # still apply bounded backoff before the next attempt.
            await self._sleep_backoff(attempt)
        assert last_error is not None
        raise last_error

    async def _bounded_request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        async with self._client.stream(method, url, follow_redirects=False, **kwargs) as response:
            # Classify errors without downloading potentially huge/untrusted error bodies.
            data = bytearray()
            if 200 <= response.status_code < 300:
                async for chunk in response.aiter_bytes(chunk_size=64 * 1024):
                    if len(data) + len(chunk) > self._max_response_bytes:
                        raise InvalidResponseError("provider response exceeds size limit")
                    data.extend(chunk)
            headers = {
                k: v for k, v in response.headers.items()
                if k.lower() not in ("content-encoding", "content-length")
            }
            return httpx.Response(
                response.status_code, headers=headers, content=bytes(data), request=response.request
            )

    def _classify(self, response: httpx.Response) -> ProviderError | None:
        status = response.status_code
        if 300 <= status < 400:
            # Redirects are never followed (SSRF safety); a redirect here
            # means the upstream changed behavior and must be investigated.
            return InvalidResponseError(f"unexpected redirect: {status}")
        if status < 400:
            return None
        if status == 429 or (status == 503 and "retry-after" in response.headers):
            # Never shorten a provider cooldown; local queue deadlines bound waiting.
            retry_after = parse_retry_after(response.headers.get("retry-after"), cap=float("inf"))
            return ThrottledError(retry_after_seconds=retry_after)
        if status == 404:
            return NotFoundError()
        if status in (401, 403):
            return ForbiddenError()
        if 400 <= status < 500:
            return InvalidResponseError(f"provider rejected request: {status}")
        return UpstreamError(f"provider error: {status}")

    async def _sleep_backoff(self, attempt: int) -> None:
        await self._sleep(self.backoff_for_attempt(attempt))
