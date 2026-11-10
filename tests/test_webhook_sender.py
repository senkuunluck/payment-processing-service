import json
from decimal import Decimal
from uuid import uuid4

import httpx
import pytest

from app.messaging.webhook_sender import WebhookSender
from app.models.payment import PaymentCurrency, PaymentStatus


@pytest.mark.asyncio
async def test_webhook_sender_sends_payment_result(
    httpx_mock,
) -> None:
    payment_id = uuid4()
    event_id = str(uuid4())

    httpx_mock.add_response(
        url="https://example.com/webhook",
        method="POST",
        status_code=200,
    )

    sender = WebhookSender(timeout=5.0)

    await sender.send(
        url="https://example.com/webhook",
        payment_id=payment_id,
        amount=str(Decimal("100.00")),
        currency=PaymentCurrency.RUB,
        status=PaymentStatus.SUCCEEDED,
        event_id=event_id,
    )

    request = httpx_mock.get_request()

    assert request is not None
    assert request.method == "POST"

    payload = json.loads(request.content)

    assert payload["event"] == "payment.completed"
    assert payload["event_id"] == event_id
    assert payload["payment_id"] == str(payment_id)
    assert payload["amount"] == "100.00"
    assert payload["currency"] == "RUB"
    assert payload["status"] == "succeeded"


@pytest.mark.asyncio
async def test_webhook_sender_raises_for_http_error(
    httpx_mock,
) -> None:
    httpx_mock.add_response(
        url="https://example.com/webhook",
        method="POST",
        status_code=500,
    )

    sender = WebhookSender()

    with pytest.raises(httpx.HTTPStatusError):
        await sender.send(
            url="https://example.com/webhook",
            payment_id=uuid4(),
            amount="100.00",
            currency=PaymentCurrency.RUB,
            status=PaymentStatus.FAILED,
            event_id=str(uuid4()),
        )


def test_webhook_sender_rejects_invalid_timeout() -> None:
    with pytest.raises(ValueError, match="Webhook timeout"):
        WebhookSender(timeout=0)
