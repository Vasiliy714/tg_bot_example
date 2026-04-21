"""Pydantic response models for Wildberries.

These models intentionally cover only the subset of fields the platform
uses; WB payloads are large and change often. Unknown fields are accepted
(``extra="ignore"``) so that schema drift never breaks the service, while
typed access to what we care about keeps the handlers strict.

Extend as needed — keep one model per endpoint to stay honest about the
contract.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(
        extra="ignore",
        populate_by_name=True,
        frozen=True,
    )


class WBStockItem(_Base):
    """One row from ``/api/v3/stocks`` (suppliers host)."""

    nm_id: int = Field(alias="nmId")
    barcode: str | None = None
    quantity: int = 0
    warehouse_id: int | None = Field(default=None, alias="warehouseId")


class WBFeedback(_Base):
    """Review item from the feedbacks API."""

    id: str
    text: str | None = None
    product_valuation: int | None = Field(default=None, alias="productValuation")
    created_date: datetime | None = Field(default=None, alias="createdDate")
    updated_date: datetime | None = Field(default=None, alias="updatedDate")
    nm_id: int | None = Field(default=None, alias="nmId")
    subject_name: str | None = Field(default=None, alias="subjectName")
    brand_name: str | None = Field(default=None, alias="brandName")
    is_able_supplier_feedback_valuation: bool | None = Field(
        default=None, alias="isAbleSupplierFeedbackValuation"
    )


class WBFeedbackList(_Base):
    """Envelope for the feedbacks API list endpoint."""

    count_unanswered: int = Field(default=0, alias="countUnanswered")
    count_archive: int = Field(default=0, alias="countArchive")
    feedbacks: list[WBFeedback] = Field(default_factory=list)
