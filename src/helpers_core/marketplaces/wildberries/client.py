"""Wildberries API client.

Wildberries splits its API across several hosts. Instead of forcing callers
to know which method lives where, this client hides the routing: each public
method points at the correct base URL internally.

Every I/O method uses the shared :class:`HttpClient`, which means:

* retries with exponential + jitter backoff on transient failures;
* circuit-breaking per seller-client instance (tokens are isolated);
* Prometheus metrics labelled ``service="wb:<area>"`` so that you can tell
  *which* WB subsystem is currently misbehaving;
* structured logs containing correlation ids propagated from handlers.
"""

from __future__ import annotations

from types import TracebackType
from typing import Any, Self

from helpers_core.config import Settings, get_settings
from helpers_core.http import HttpClient, HttpClientConfig, HttpResponseError
from helpers_core.logging import get_logger
from helpers_core.marketplaces.wildberries.errors import (
    WildberriesError,
    map_http_error,
)
from helpers_core.marketplaces.wildberries.models import (
    WBFeedbackList,
    WBStockItem,
)

logger = get_logger(__name__)


class WildberriesClient:
    """Facade over the main WB hosts.

    The client holds one HTTP session per host so that aiohttp connection
    pools stay hot across calls. All sessions share the same bearer token.
    """

    def __init__(
        self,
        *,
        api_token: str,
        settings: Settings | None = None,
    ) -> None:
        if not api_token:
            raise ValueError("api_token is required")

        self._settings = settings or get_settings()
        self._token = api_token

        headers = {"Authorization": api_token}

        self._suppliers = HttpClient(
            HttpClientConfig.from_settings(
                self._settings,
                base_url=self._settings.marketplaces.wb_api_base_url,
                default_headers=headers,
                service_label="wb:suppliers",
            )
        )
        self._statistics = HttpClient(
            HttpClientConfig.from_settings(
                self._settings,
                base_url=self._settings.marketplaces.wb_stats_api_base_url,
                default_headers=headers,
                service_label="wb:statistics",
            )
        )
        self._feedbacks = HttpClient(
            HttpClientConfig.from_settings(
                self._settings,
                base_url=self._settings.marketplaces.wb_feedbacks_api_base_url,
                default_headers=headers,
                service_label="wb:feedbacks",
            )
        )
        self._content = HttpClient(
            HttpClientConfig.from_settings(
                self._settings,
                base_url=self._settings.marketplaces.wb_content_api_base_url,
                default_headers=headers,
                service_label="wb:content",
            )
        )
        self._advert = HttpClient(
            HttpClientConfig.from_settings(
                self._settings,
                base_url=self._settings.marketplaces.wb_advert_api_base_url,
                default_headers=headers,
                service_label="wb:advert",
            )
        )

    # ------------------------------------------------------------------ lifecycle

    async def start(self) -> None:
        for client in self._all_clients:
            await client.start()

    async def close(self) -> None:
        for client in self._all_clients:
            await client.close()

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

    @property
    def _all_clients(self) -> tuple[HttpClient, ...]:
        return (
            self._suppliers,
            self._statistics,
            self._feedbacks,
            self._content,
            self._advert,
        )

    # ------------------------------------------------------------------ helpers

    async def _get_json(self, client: HttpClient, path: str, **kwargs: Any) -> Any:
        try:
            return await client.get_json(path, **kwargs)
        except HttpResponseError as exc:
            raise map_http_error(exc) from exc

    async def _post_json(self, client: HttpClient, path: str, **kwargs: Any) -> Any:
        try:
            return await client.post_json(path, **kwargs)
        except HttpResponseError as exc:
            raise map_http_error(exc) from exc

    # ------------------------------------------------------------------ endpoints

    async def ping(self) -> bool:
        """Cheap credentials check.

        The content API's ``/ping`` is the lowest-cost authenticated
        endpoint; a 200 means the token is valid.
        """
        try:
            await self._get_json(self._content, "/ping")
            return True
        except WildberriesError:
            return False

    async def list_feedbacks(
        self,
        *,
        is_answered: bool = False,
        take: int = 100,
        skip: int = 0,
    ) -> WBFeedbackList:
        """``GET /api/v1/feedbacks`` — list reviews for the seller.

        Args:
            is_answered: include only answered / unanswered reviews.
            take: page size, capped by WB at 5000.
            skip: offset.
        """
        if not 1 <= take <= 5000:
            raise ValueError("take must be 1..5000")
        raw = await self._get_json(
            self._feedbacks,
            "/api/v1/feedbacks",
            params={"isAnswered": str(is_answered).lower(), "take": take, "skip": skip},
        )
        payload = raw.get("data", raw) if isinstance(raw, dict) else raw
        return WBFeedbackList.model_validate(payload)

    async def answer_feedback(self, feedback_id: str, text: str) -> None:
        """``POST /api/v1/feedbacks/answer`` — publish an answer to a review."""
        if not text.strip():
            raise ValueError("answer text must not be empty")
        await self._post_json(
            self._feedbacks,
            "/api/v1/feedbacks/answer",
            json={"id": feedback_id, "text": text},
        )

    async def list_stocks(self, *, date_from: str) -> list[WBStockItem]:
        """``GET /api/v1/supplier/stocks`` on the statistics host.

        ``date_from`` is ISO-8601 (e.g. ``"2024-01-01T00:00:00"``).
        """
        raw = await self._get_json(
            self._statistics,
            "/api/v1/supplier/stocks",
            params={"dateFrom": date_from},
        )
        if not isinstance(raw, list):
            raise WildberriesError(f"Unexpected stocks payload: {type(raw)}")
        return [WBStockItem.model_validate(item) for item in raw]
