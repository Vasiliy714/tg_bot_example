"""Domain-specific Wildberries errors."""

from __future__ import annotations

from helpers_core.http import HttpResponseError


class WildberriesError(RuntimeError):
    """Base class for Wildberries-side failures that handlers should catch."""


class WildberriesAuthError(WildberriesError):
    """Raised on 401/403 — the seller's token is invalid or revoked."""


class WildberriesRateLimitError(WildberriesError):
    """Raised on 429 — the caller should back off."""


def map_http_error(exc: HttpResponseError) -> WildberriesError:
    """Translate a generic HTTP error to a domain-specific one."""
    if exc.status in (401, 403):
        return WildberriesAuthError(f"Unauthorized: {exc.body[:200]}")
    if exc.status == 429:
        return WildberriesRateLimitError("Rate limit exceeded")
    return WildberriesError(f"Wildberries API error {exc.status}: {exc.body[:200]}")
