"""Smoke tests for the Wildberries client (aioresponses-mocked)."""

from __future__ import annotations

import pytest
from aioresponses import aioresponses

from helpers_core.marketplaces.wildberries import (
    WildberriesAuthError,
    WildberriesClient,
)


@pytest.mark.asyncio
async def test_ping_succeeds_on_2xx() -> None:
    with aioresponses() as mocked:
        mocked.get("https://content-api.wildberries.ru/ping", payload={})
        async with WildberriesClient(api_token="token") as client:
            assert await client.ping() is True


@pytest.mark.asyncio
async def test_auth_error_mapped() -> None:
    with aioresponses() as mocked:
        mocked.get(
            "https://feedbacks-api.wildberries.ru/api/v1/feedbacks?isAnswered=false&skip=0&take=10",
            status=401,
            body="bad token",
        )
        async with WildberriesClient(api_token="token") as client:
            with pytest.raises(WildberriesAuthError):
                await client.list_feedbacks(take=10)
