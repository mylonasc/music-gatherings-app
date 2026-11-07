"""Shared error taxonomy and Retry-After parsing for provider traffic."""

import email.utils
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderError(Exception):
    code: str
    message: str
    retryable: bool = False
    retry_after_seconds: float | None = None

    def to_envelope(self) -> dict[str, Any]:
        envelope: dict[str, Any] = {
            "error": {"code": self.code, "message": self.message, "retryable": self.retryable}
        }
        if self.retry_after_seconds is not None:
            envelope["error"]["retry_after_seconds"] = self.retry_after_seconds
        return envelope


class ThrottledError(ProviderError):
    def __init__(self, message: str = "provider throttled", retry_after_seconds: float = 30.0):
        super().__init__(
            code="throttled",
            message=message,
            retryable=True,
            retry_after_seconds=retry_after_seconds,
        )


class UpstreamError(ProviderError):
    def __init__(self, message: str = "provider unavailable"):
        super().__init__(code="upstream_unavailable", message=message, retryable=True)


class NotFoundError(ProviderError):
    def __init__(self, message: str = "not found"):
        super().__init__(code="not_found", message=message, retryable=False)


class ForbiddenError(ProviderError):
    def __init__(self, message: str = "provider refused the request"):
        super().__init__(code="forbidden", message=message, retryable=False)


class NotConfiguredError(ProviderError):
    def __init__(self, message: str = "provider not configured"):
        super().__init__(code="not_configured", message=message, retryable=False)


class ProviderUnavailableError(ProviderError):
    def __init__(self, message: str = "provider unavailable"):
        super().__init__(code="provider_unavailable", message=message, retryable=False)


class InvalidResponseError(ProviderError):
    def __init__(self, message: str = "invalid provider response"):
        super().__init__(code="invalid_response", message=message, retryable=False)


def parse_retry_after(
    value: str | None,
    *,
    now: float | None = None,
    default: float = 30.0,
    cap: float = 300.0,
) -> float:
    """Parse a Retry-After header (delta seconds or HTTP date), bounded by cap."""
    if not value:
        return default
    value = value.strip()
    try:
        return max(0.0, min(cap, float(value)))
    except ValueError:
        pass
    try:
        moment = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return default
    if moment is None:
        return default
    base = now if now is not None else time.time()
    return max(0.0, min(cap, moment.timestamp() - base))
