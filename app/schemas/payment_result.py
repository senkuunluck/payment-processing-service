from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from app.models.payment import PaymentCurrency, PaymentStatus


@dataclass(frozen=True, slots=True)
class PaymentProcessingResult:
    """Result of payment processing, including webhook destination."""

    payment_id: UUID
    amount: Decimal
    currency: PaymentCurrency
    status: PaymentStatus
    webhook_url: str
