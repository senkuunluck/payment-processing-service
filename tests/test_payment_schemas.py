from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.models.payment import PaymentCurrency, PaymentStatus
from app.schemas.payment import PaymentCreate, PaymentResponse


def test_payment_create_valid_data() -> None:
    payment = PaymentCreate(
        amount="1500.00",
        currency="RUB",
        description="Оплата заказа",
        metadata={"order_id": "123"},
        webhook_url="https://example.com/webhook",
    )

    assert payment.amount == Decimal("1500.00")
    assert payment.currency == PaymentCurrency.RUB
    assert payment.description == "Оплата заказа"
    assert payment.metadata == {"order_id": "123"}


def test_payment_create_rejects_zero_amount() -> None:
    with pytest.raises(ValidationError):
        PaymentCreate(
            amount="0",
            currency="RUB",
            description="Оплата заказа",
            webhook_url="https://example.com/webhook",
        )


def test_payment_create_rejects_invalid_currency() -> None:
    with pytest.raises(ValidationError):
        PaymentCreate(
            amount="100.00",
            currency="GBP",
            description="Оплата заказа",
            webhook_url="https://example.com/webhook",
        )


def test_payment_create_rejects_invalid_webhook_url() -> None:
    with pytest.raises(ValidationError):
        PaymentCreate(
            amount="100.00",
            currency="RUB",
            description="Оплата заказа",
            webhook_url="not-a-url",
        )


def test_payment_response_from_attributes() -> None:
    payment_id = uuid4()
    created = datetime.now(UTC)

    class FakePayment:
        id = payment_id
        amount = Decimal("1500.00")
        currency = PaymentCurrency.RUB
        description = "Оплата заказа"
        metadata_json = {"order_id": "123"}
        status = PaymentStatus.PENDING
        created_at = created
        processed_at = None

    response = PaymentResponse.model_validate(FakePayment())

    assert response.id == payment_id
    assert response.amount == Decimal("1500.00")
    assert response.metadata == {"order_id": "123"}
    assert response.status == PaymentStatus.PENDING
