
import asyncio
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select

from app.db.session import async_session_factory
from app.models.outbox import Outbox
from app.models.payment import Payment
from app.schemas.payment import PaymentCreate
from app.services.payment import (
    IdempotencyConflictError,
    PaymentService,
)


def make_payment_data(
    amount: str = "1500.00",
) -> PaymentCreate:
    return PaymentCreate(
        amount=amount,
        currency="RUB",
        description="Test payment",
        metadata={"order_id": "123"},
        webhook_url="https://example.com/webhook",
    )


async def cleanup_payment(idempotency_key: str) -> None:
    """Remove test payment and its outbox event."""

    async with async_session_factory() as session:
        async with session.begin():
            payment = await session.scalar(
                select(Payment).where(
                    Payment.idempotency_key == idempotency_key
                )
            )

            if payment is not None:
                await session.execute(
                    delete(Outbox).where(
                        Outbox.payload["payment_id"].as_string()
                        == str(payment.id)
                    )
                )
                await session.delete(payment)


@pytest.mark.asyncio
async def test_create_payment_and_outbox() -> None:
    key = f"test-{uuid4()}"

    try:
        async with async_session_factory() as session:
            service = PaymentService(session)
            payment = await service.create_payment(
                make_payment_data(),
                key,
            )
            payment_id = payment.id

        async with async_session_factory() as session:
            saved_payment = await session.scalar(
                select(Payment).where(Payment.id == payment_id)
            )
            outbox_count = await session.scalar(
                select(func.count())
                .select_from(Outbox)
                .where(
                    Outbox.payload["payment_id"].as_string()
                    == str(payment_id)
                )
            )

        assert saved_payment is not None
        assert saved_payment.idempotency_key == key
        assert outbox_count == 1
    finally:
        await cleanup_payment(key)


@pytest.mark.asyncio
async def test_repeated_request_returns_existing_payment() -> None:
    key = f"test-{uuid4()}"

    try:
        async with async_session_factory() as session:
            service = PaymentService(session)
            first_payment = await service.create_payment(
                make_payment_data(),
                key,
            )
            first_id = first_payment.id

        async with async_session_factory() as session:
            service = PaymentService(session)
            second_payment = await service.create_payment(
                make_payment_data(),
                key,
            )

        assert second_payment.id == first_id

        async with async_session_factory() as session:
            outbox_count = await session.scalar(
                select(func.count())
                .select_from(Outbox)
                .where(
                    Outbox.payload["payment_id"].as_string()
                    == str(first_id)
                )
            )

        assert outbox_count == 1
    finally:
        await cleanup_payment(key)


@pytest.mark.asyncio
async def test_reused_key_with_different_data_raises_conflict() -> None:
    key = f"test-{uuid4()}"

    try:
        async with async_session_factory() as session:
            service = PaymentService(session)
            await service.create_payment(make_payment_data(), key)

        async with async_session_factory() as session:
            service = PaymentService(session)

            with pytest.raises(IdempotencyConflictError):
                await service.create_payment(
                    make_payment_data(amount="2000.00"),
                    key,
                )
    finally:
        await cleanup_payment(key)


@pytest.mark.asyncio
async def test_concurrent_requests_create_one_payment() -> None:
    key = f"test-{uuid4()}"

    async def create_payment():
        async with async_session_factory() as session:
            service = PaymentService(session)
            return await service.create_payment(
                make_payment_data(),
                key,
            )

    try:
        first, second = await asyncio.gather(
            create_payment(),
            create_payment(),
        )

        assert first.id == second.id

        async with async_session_factory() as session:
            payment_count = await session.scalar(
                select(func.count())
                .select_from(Payment)
                .where(Payment.idempotency_key == key)
            )
            outbox_count = await session.scalar(
                select(func.count())
                .select_from(Outbox)
                .where(
                    Outbox.payload["payment_id"].as_string()
                    == str(first.id)
                )
            )

        assert payment_count == 1
        assert outbox_count == 1
    finally:
        await cleanup_payment(key)
