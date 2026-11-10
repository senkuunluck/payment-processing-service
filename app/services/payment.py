from uuid import uuid4

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox import Outbox
from app.models.payment import Payment, PaymentStatus
from app.repositories.payment import PaymentRepository
from app.schemas.payment import PaymentCreate


class IdempotencyConflictError(Exception):
    """Raised when an idempotency key is reused with different data."""


class PaymentService:
    """Business logic for payment creation."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.payment_repository = PaymentRepository(session)

    @staticmethod
    def _has_same_data(
        payment: Payment,
        data: PaymentCreate,
    ) -> bool:
        """Check whether an existing payment matches the new request."""

        return (
            payment.amount == data.amount
            and payment.currency == data.currency
            and payment.description == data.description
            and payment.metadata_json == data.metadata
            and payment.webhook_url == str(data.webhook_url)
        )

    async def create_payment(
        self,
        data: PaymentCreate,
        idempotency_key: str,
    ) -> Payment:
        """Create a payment and its outbox event atomically."""

        try:
            async with self.session.begin():
                existing_payment = await self.payment_repository.get_by_idempotency_key(
                    idempotency_key
                )

                if existing_payment is not None:
                    if not self._has_same_data(existing_payment, data):
                        raise IdempotencyConflictError(
                            "Idempotency key was already used with different payment data."
                        )

                    return existing_payment

                payment = Payment(
                    amount=data.amount,
                    currency=data.currency,
                    description=data.description,
                    metadata_json=data.metadata,
                    idempotency_key=idempotency_key,
                    webhook_url=str(data.webhook_url),
                    status=PaymentStatus.PENDING,
                )

                await self.payment_repository.create(payment)

                outbox_event = Outbox(
                    event_type="payment.created",
                    payload={
                        "event_id": str(uuid4()),
                        "payment_id": str(payment.id),
                        "amount": str(payment.amount),
                        "currency": payment.currency.value,
                        "status": payment.status.value,
                    },
                )

                self.session.add(outbox_event)
                await self.session.flush()

                return payment

        except IntegrityError:
            # Another concurrent request may have inserted this key first.
            await self.session.rollback()

            existing_payment = await self.payment_repository.get_by_idempotency_key(idempotency_key)

            if existing_payment is None:
                raise

            if not self._has_same_data(existing_payment, data):
                raise IdempotencyConflictError(
                    "Idempotency key was already used with different payment data."
                ) from None

            return existing_payment
