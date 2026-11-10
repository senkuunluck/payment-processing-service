import asyncio
import logging
import random
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.payment import Payment, PaymentStatus
from app.schemas.payment_event import PaymentCreatedEvent
from app.schemas.payment_result import PaymentProcessingResult

logger = logging.getLogger(__name__)


class PaymentProcessor:
    """Processes payments received from RabbitMQ."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        self.session_factory = session_factory

    @staticmethod
    def _build_result(payment: Payment) -> PaymentProcessingResult:
        return PaymentProcessingResult(
            payment_id=payment.id,
            amount=payment.amount,
            currency=payment.currency,
            status=payment.status,
            webhook_url=payment.webhook_url,
        )

    async def process(
        self,
        event: PaymentCreatedEvent,
    ) -> PaymentProcessingResult:
        """Process a payment once and return its persisted result."""

        async with self.session_factory() as session:
            payment = await session.get(Payment, event.payment_id)

            if payment is None:
                raise LookupError(f"Payment {event.payment_id} was not found.")

            if payment.status != PaymentStatus.PENDING:
                logger.info(
                    "Payment %s already has status %s",
                    payment.id,
                    payment.status,
                )
                return self._build_result(payment)

        delay = random.uniform(2.0, 5.0)
        await asyncio.sleep(delay)

        result = PaymentStatus.SUCCEEDED if random.random() < 0.9 else PaymentStatus.FAILED

        async with self.session_factory() as session:
            async with session.begin():
                statement = select(Payment).where(Payment.id == event.payment_id).with_for_update()

                payment = await session.scalar(statement)

                if payment is None:
                    raise LookupError(f"Payment {event.payment_id} was not found.")

                if payment.status != PaymentStatus.PENDING:
                    logger.info(
                        "Payment %s was processed by another delivery",
                        payment.id,
                    )
                    return self._build_result(payment)

                payment.status = result
                payment.processed_at = datetime.now(UTC)

                await session.flush()

                processing_result = self._build_result(payment)

        logger.info(
            "Payment %s processed with status %s",
            processing_result.payment_id,
            processing_result.status,
        )

        return processing_result
