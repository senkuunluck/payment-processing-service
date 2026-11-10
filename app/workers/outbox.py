import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings
from app.messaging.protocols import MessagePublisher
from app.services.outbox_publisher import OutboxPublisher

logger = logging.getLogger(__name__)


class OutboxWorker:
    """Periodically publish unpublished Outbox events."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        message_publisher: MessagePublisher,
        settings: Settings,
    ) -> None:
        self.session_factory = session_factory
        self.message_publisher = message_publisher
        self.poll_interval = settings.outbox_poll_interval
        self.batch_size = settings.outbox_batch_size
        self._running = False

    async def run(self) -> None:
        """Run the Outbox polling loop."""
        self._running = True
        logger.info("Outbox worker started")

        try:
            while self._running:
                try:
                    await self.process_batch()
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("Outbox worker failed to process a batch")

                await asyncio.sleep(self.poll_interval)
        finally:
            self._running = False
            logger.info("Outbox worker stopped")

    async def process_batch(self) -> int:
        """Publish one batch of Outbox events."""
        async with self.session_factory() as session:
            async with session.begin():
                publisher = OutboxPublisher(
                    session=session,
                    message_publisher=self.message_publisher,
                )
                published_count = await publisher.publish_batch(
                    batch_size=self.batch_size,
                )

            if published_count:
                logger.info(
                    "Published %s Outbox events",
                    published_count,
                )

            return published_count
