"""Domain-specific Ozon errors."""

from __future__ import annotations

from helpers_core.http import HttpResponseError


class OzonError(RuntimeError):
    """Base class for Ozon-side failures."""


class OzonAuthError(OzonError):
    """401/403 — the seller's `Client-Id` / `Api-Key` pair is invalid."""


class OzonRateLimitError(OzonError):
    """429 — the caller must back off."""


def map_http_error(exc: HttpResponseError) -> OzonError:
    if exc.status in (401, 403):
        return OzonAuthError(f"Unauthorized: {exc.body[:200]}")
    if exc.status == 429:
        return OzonRateLimitError("Rate limit exceeded")
    return OzonError(f"Ozon API error {exc.status}: {exc.body[:200]}")
