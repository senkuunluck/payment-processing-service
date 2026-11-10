from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox import Outbox


class OutboxRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_unpublished(self, limit: int = 100) -> list[Outbox]:
        if limit < 1:
            raise ValueError("Limit must be greater than zero.")

        statement = (
            select(Outbox)
            .where(Outbox.published_at.is_(None))
            .order_by(Outbox.created_at, Outbox.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
        )

        result = await self.session.execute(statement)

        return list(result.scalars().all())

    async def mark_as_published(self, event: Outbox) -> None:
        event.published_at = func.now()

        await self.session.flush()
        await self.session.refresh(event)

    async def record_failure(
        self,
        event: Outbox,
        error: str,
    ) -> None:
        event.attempts += 1
        event.last_error = error

        await self.session.flush()
