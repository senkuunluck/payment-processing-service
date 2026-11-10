import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.messaging.protocols import MessagePublisher
from app.repositories.outbox import OutboxRepository

logger = logging.getLogger(__name__)


class OutboxPublisher:
    """Publish unpublished Outbox events to a message broker."""

    def __init__(
        self,
        session: AsyncSession,
        message_publisher: MessagePublisher,
    ) -> None:
        self.repository = OutboxRepository(session)
        self.message_publisher = message_publisher

    async def publish_batch(self, batch_size: int = 100) -> int:
        """Publish a batch of unpublished events.

        Return the number of successfully published events.
        The caller is responsible for committing the transaction.
        """

        if batch_size < 1:
            raise ValueError("Batch size must be greater than zero.")

        published_count = 0

        events = await self.repository.get_unpublished(limit=batch_size)

        for event in events:
            try:
                await self.message_publisher.publish(
                    event.event_type,
                    event.payload,
                )

                await self.repository.mark_as_published(event)
                published_count += 1

            except Exception as exc:
                await self.repository.record_failure(
                    event,
                    str(exc),
                )

                logger.exception(
                    "Failed to publish Outbox event %s",
                    event.id,
                )

        return published_count
