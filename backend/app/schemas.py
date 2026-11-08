from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LineItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    description: str
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    amount: Decimal | None = None


class InvoiceData(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vendor_name: str | None = None
    invoice_number: str | None = None
    invoice_date: str | None = None
    total: Decimal | None = None
    currency: str | None = None
    line_items: list[LineItem] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class ReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    corrections: dict[str, Any]
    reviewer: str = "reviewer"
