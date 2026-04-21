"""Pydantic response models for Ozon."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        frozen=True,
    )


class OzonProduct(_Base):
    """One row from ``/v2/product/list``."""

    product_id: int
    offer_id: str
    archived: bool = False


class OzonProductList(_Base):
    """Envelope returned by ``/v2/product/list``."""

    items: list[OzonProduct] = Field(default_factory=list)
    total: int = 0
    last_id: str = ""


class OzonReview(_Base):
    """Review (``/v1/review/list``)."""

    id: str
    sku: int | None = None
    text: str | None = None
    rating: int | None = None
    published_at: datetime | None = None
    status: str | None = None
