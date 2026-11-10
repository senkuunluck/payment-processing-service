from uuid import UUID
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox import Outbox


class OutboxRepository:
    """Repository for Outbox database operations."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_unpublished(self, limit: int = 100) -> list[Outbox]:
        """Return unpublished events ordered by creation time."""

        if limit < 1:
            raise ValueError("Limit must be greater than zero.")

        statement = (
            select(Outbox)
            .where(Outbox.published_at.is_(None))
            .order_by(Outbox.created_at, Outbox.id)
            .limit(limit)
        )

        result = await self.session.execute(statement)

        return list(result.scalars().all())

    async def mark_as_published(self, event: Outbox) -> None:
        """Mark an event as successfully published."""

        event.published_at = func.now()
        await self.session.flush()
        await self.session.refresh(event)

    async def record_failure(self, event: Outbox, error: str) -> None:
        """Record a failed publishing attempt."""

        event.attempts += 1
        event.last_error = error

        await self.session.flush()
