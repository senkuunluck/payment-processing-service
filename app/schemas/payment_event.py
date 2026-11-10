from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models.payment import PaymentCurrency, PaymentStatus


class PaymentCreatedEvent(BaseModel):
    """Event emitted when a payment is created."""

    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    payment_id: UUID
    amount: Decimal = Field(gt=0)
    currency: PaymentCurrency
    status: PaymentStatus


class PaymentEventEnvelope(BaseModel):
    """RabbitMQ message envelope."""

    model_config = ConfigDict(extra="forbid")

    event_type: Literal["payment.created"]
    payload: PaymentCreatedEvent
