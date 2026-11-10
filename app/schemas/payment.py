from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models.payment import PaymentCurrency, PaymentStatus


class PaymentCreate(BaseModel):
    """Schema for creating a payment."""

    amount: Decimal = Field(
        gt=0,
        max_digits=12,
        decimal_places=2,
        description="Payment amount",
    )
    currency: PaymentCurrency
    description: str = Field(min_length=1, max_length=500)
    metadata: dict[str, Any] = Field(default_factory=dict)
    webhook_url: HttpUrl


class PaymentResponse(BaseModel):
    """Schema returned to the API client."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    amount: Decimal
    currency: PaymentCurrency
    description: str
    metadata: dict[str, Any] = Field(
        validation_alias="metadata_json",
    )
    status: PaymentStatus
    created_at: datetime
    processed_at: datetime | None
