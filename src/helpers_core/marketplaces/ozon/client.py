"""Ozon seller API client.

Ozon authenticates requests with a ``Client-Id`` + ``Api-Key`` header pair
and exposes two related APIs on different hosts: ``api-seller`` (core
catalog / orders / reviews) and ``performance`` (ads). This client
encapsulates both.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Self

from helpers_core.config import Settings, get_settings
from helpers_core.http import HttpClient, HttpClientConfig, HttpResponseError
from helpers_core.logging import get_logger
from helpers_core.marketplaces.ozon.errors import (
    OzonError,
    map_http_error,
)
from helpers_core.marketplaces.ozon.models import OzonProductList, OzonReview

logger = get_logger(__name__)


class OzonClient:
    """Ozon seller-side API facade.

    Parameters:
        client_id: Ozon ``Client-Id`` of the seller account.
        api_key: Seller-level ``Api-Key``.
        perf_client_id / perf_client_secret: Credentials for the
            performance (ads) API; optional — omit if the seller does not
            use ads.
    """

    def __init__(
        self,
        *,
        client_id: str,
        api_key: str,
        perf_client_id: str | None = None,
        perf_client_secret: str | None = None,
        settings: Settings | None = None,
    ) -> None:
        if not client_id or not api_key:
            raise ValueError("client_id and api_key are required")

        self._settings = settings or get_settings()

        seller_headers = {
            "Client-Id": client_id,
            "Api-Key": api_key,
            "Content-Type": "application/json",
        }

        self._seller = HttpClient(
            HttpClientConfig.from_settings(
                self._settings,
                base_url=self._settings.marketplaces.ozon_api_base_url,
                default_headers=seller_headers,
                service_label="ozon:seller",
            )
        )

        self._performance: HttpClient | None = None
        if perf_client_id and perf_client_secret:
            # The performance API uses OAuth2 client-credentials — the
            # token is fetched lazily from :meth:`_performance_token` on
            # first use. Storing the creds here keeps refresh cheap.
            self._perf_client_id = perf_client_id
            self._perf_client_secret = perf_client_secret
            self._performance = HttpClient(
                HttpClientConfig.from_settings(
                    self._settings,
                    base_url=self._settings.marketplaces.ozon_performance_api_base_url,
                    default_headers={"Content-Type": "application/json"},
                    service_label="ozon:performance",
                )
            )

    # ------------------------------------------------------------------ lifecycle

    async def start(self) -> None:
        await self._seller.start()
        if self._performance is not None:
            await self._performance.start()

    async def close(self) -> None:
        await self._seller.close()
        if self._performance is not None:
            await self._performance.close()

    async def __aenter__(self) -> Self:
        await self.start()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.close()

    # ------------------------------------------------------------------ endpoints

    async def ping(self) -> bool:
        """Validate credentials via the cheapest authenticated endpoint."""
        try:
            await self._post_json(self._seller, "/v1/category/tree", json={"language": "EN"})
            return True
        except OzonError:
            return False

    async def list_products(
        self,
        *,
        last_id: str = "",
        limit: int = 100,
    ) -> OzonProductList:
        """``POST /v2/product/list``."""
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be 1..1000")
        raw = await self._post_json(
            self._seller,
            "/v2/product/list",
            json={"filter": {}, "last_id": last_id, "limit": limit},
        )
        payload = raw.get("result", raw) if isinstance(raw, dict) else raw
        return OzonProductList.model_validate(payload)

    async def list_reviews(
        self,
        *,
        last_id: str = "",
        limit: int = 100,
        status: str = "ALL",
    ) -> list[OzonReview]:
        """``POST /v1/review/list``. Requires review-module subscription."""
        raw = await self._post_json(
            self._seller,
            "/v1/review/list",
            json={"last_id": last_id, "limit": limit, "status": status},
        )
        items: list[Any] = []
        if isinstance(raw, dict):
            items = raw.get("reviews") or raw.get("result") or []
        return [OzonReview.model_validate(item) for item in items]

    async def answer_review(self, review_id: str, text: str) -> None:
        if not text.strip():
            raise ValueError("answer text must not be empty")
        await self._post_json(
            self._seller,
            "/v1/review/comment/create",
            json={"review_id": review_id, "text": text, "mark_review_as_processed": True},
        )

    # ------------------------------------------------------------------ helpers

    async def _post_json(self, client: HttpClient, path: str, **kwargs: Any) -> Any:
        try:
            return await client.post_json(path, **kwargs)
        except HttpResponseError as exc:
            raise map_http_error(exc) from exc
