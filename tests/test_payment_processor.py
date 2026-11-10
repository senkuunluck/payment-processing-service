import asyncio
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.payment import Payment, PaymentCurrency, PaymentStatus
from app.schemas.payment_event import PaymentCreatedEvent
from app.services.payment_processor import PaymentProcessor


async def create_test_payment() -> Payment:
    """Create a payment in the test database."""

    async with async_session_factory() as session:
        async with session.begin():
            payment = Payment(
                amount=Decimal("1500.00"),
                currency=PaymentCurrency.RUB,
                description="Payment processor test",
                metadata_json={"test": True},
                idempotency_key=f"processor-test-{uuid4()}",
                webhook_url="https://example.com/webhook",
            )
            session.add(payment)
            await session.flush()
            await session.refresh(payment)

            return payment


async def cleanup_payment(payment_id: object) -> None:
    """Remove a test payment from the database."""

    async with async_session_factory() as session:
        async with session.begin():
            payment = await session.get(Payment, payment_id)
            if payment is not None:
                await session.delete(payment)


def make_event(payment: Payment) -> PaymentCreatedEvent:
    """Build a payment-created event."""

    return PaymentCreatedEvent(
        event_id=uuid4(),
        payment_id=payment.id,
        amount=payment.amount,
        currency=payment.currency,
        status=PaymentStatus.PENDING,
    )


@pytest.fixture
def processor() -> PaymentProcessor:
    return PaymentProcessor(session_factory=async_session_factory)


@pytest.mark.asyncio
async def test_process_payment_success(
    processor: PaymentProcessor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payment = await create_test_payment()

    monkeypatch.setattr("app.services.payment_processor.random.uniform", lambda a, b: 3.0)
    monkeypatch.setattr("app.services.payment_processor.asyncio.sleep", AsyncMock())
    monkeypatch.setattr("app.services.payment_processor.random.random", lambda: 0.5)

    try:
        result = await processor.process(make_event(payment))

        assert result.status == PaymentStatus.SUCCEEDED

        async with async_session_factory() as session:
            saved_payment = await session.get(Payment, payment.id)

        assert saved_payment is not None
        assert saved_payment.status == PaymentStatus.SUCCEEDED
        assert saved_payment.processed_at is not None
    finally:
        await cleanup_payment(payment.id)


@pytest.mark.asyncio
async def test_process_payment_failure(
    processor: PaymentProcessor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payment = await create_test_payment()

    monkeypatch.setattr("app.services.payment_processor.random.uniform", lambda a, b: 4.0)
    monkeypatch.setattr("app.services.payment_processor.asyncio.sleep", AsyncMock())
    monkeypatch.setattr("app.services.payment_processor.random.random", lambda: 0.95)

    try:
        result = await processor.process(make_event(payment))

        assert result.status == PaymentStatus.FAILED

        async with async_session_factory() as session:
            saved_payment = await session.get(Payment, payment.id)

        assert saved_payment is not None
        assert saved_payment.status == PaymentStatus.FAILED
        assert saved_payment.processed_at is not None
    finally:
        await cleanup_payment(payment.id)


@pytest.mark.asyncio
async def test_process_nonexistent_payment(
    processor: PaymentProcessor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleep_mock = AsyncMock()
    monkeypatch.setattr("app.services.payment_processor.asyncio.sleep", sleep_mock)

    event = PaymentCreatedEvent(
        event_id=uuid4(),
        payment_id=uuid4(),
        amount=Decimal("100.00"),
        currency=PaymentCurrency.RUB,
        status=PaymentStatus.PENDING,
    )

    with pytest.raises(LookupError, match="was not found"):
        await processor.process(event)

    sleep_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_repeated_event_does_not_process_payment_again(
    processor: PaymentProcessor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payment = await create_test_payment()
    sleep_mock = AsyncMock()

    monkeypatch.setattr("app.services.payment_processor.random.uniform", lambda a, b: 3.0)
    monkeypatch.setattr("app.services.payment_processor.asyncio.sleep", sleep_mock)
    monkeypatch.setattr("app.services.payment_processor.random.random", lambda: 0.5)

    try:
        event = make_event(payment)

        first_result = await processor.process(event)
        second_result = await processor.process(event)

        assert first_result.status == PaymentStatus.SUCCEEDED
        assert second_result.status == PaymentStatus.SUCCEEDED
        sleep_mock.assert_awaited_once()
    finally:
        await cleanup_payment(payment.id)


@pytest.mark.asyncio
async def test_concurrent_processing_keeps_one_final_status(
    processor: PaymentProcessor,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payment = await create_test_payment()

    async def fake_sleep(delay: float) -> None:
        return None

    monkeypatch.setattr("app.services.payment_processor.random.uniform", lambda a, b: 3.0)
    monkeypatch.setattr("app.services.payment_processor.asyncio.sleep", fake_sleep)
    monkeypatch.setattr("app.services.payment_processor.random.random", lambda: 0.5)

    try:
        event = make_event(payment)

        first_result, second_result = await asyncio.gather(
            processor.process(event),
            processor.process(event),
        )

        assert first_result.status == second_result.status
        assert first_result.status in {
            PaymentStatus.SUCCEEDED,
            PaymentStatus.FAILED,
        }

        async with async_session_factory() as session:
            saved_payment = await session.scalar(select(Payment).where(Payment.id == payment.id))

        assert saved_payment is not None
        assert saved_payment.status == first_result.status
    finally:
        await cleanup_payment(payment.id)
