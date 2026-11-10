import logging
from typing import Any
from uuid import UUID

import httpx

from app.models.payment import PaymentCurrency, PaymentStatus

logger = logging.getLogger(__name__)


class WebhookSender:
    """Sends payment result notifications to client webhook URLs."""

    def __init__(self, timeout: float = 10.0) -> None:
        if timeout <= 0:
            raise ValueError("Webhook timeout must be greater than zero.")

        self.timeout = timeout

    async def send(
        self,
        url: str,
        payment_id: UUID,
        amount: str,
        currency: PaymentCurrency,
        status: PaymentStatus,
        event_id: str,
    ) -> None:
        """Send a payment result to the client's webhook endpoint."""

        payload: dict[str, Any] = {
            "event": "payment.completed",
            "event_id": event_id,
            "payment_id": str(payment_id),
            "amount": amount,
            "currency": currency.value,
            "status": status.value,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()

        logger.info(
            "Webhook delivered for payment %s",
            payment_id,
        )
