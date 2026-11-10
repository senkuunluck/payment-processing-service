from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import Payment


class PaymentRepository:
    """Repository for payment database operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, payment: Payment) -> Payment:
        """Add a payment to the current database transaction."""

        self.session.add(payment)

        await self.session.flush()
        await self.session.refresh(payment)

        return payment

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> Payment | None:
        """Find a payment by its idempotency key."""

        statement = select(Payment).where(Payment.idempotency_key == idempotency_key)

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()

    async def get_by_id(self, payment_id: UUID) -> Payment | None:
        """Find a payment by its ID."""

        statement = select(Payment).where(Payment.id == payment_id)

        result = await self.session.execute(statement)

        return result.scalar_one_or_none()
