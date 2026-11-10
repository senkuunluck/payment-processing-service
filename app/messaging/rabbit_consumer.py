from typing import Any

from faststream import AckPolicy
from faststream.rabbit import RabbitBroker, RabbitQueue


class RabbitMQConsumer:
    """Consumes payment events with exponential retry and DLQ support."""

    def __init__(
        self,
        url: str,
        queue_name: str = "payments.new",
        retry_queue_name: str = "payment_events_retry_v2",
        dlq_name: str = "payment_events_dlq",
        retry_delay_ms: int = 5000,
    ) -> None:
        self.broker = RabbitBroker(url)

        self.queue = RabbitQueue(
            name=queue_name,
            durable=True,
        )

        self.retry_queue_2s = RabbitQueue(
            name=f"{retry_queue_name}_2s",
            durable=True,
            arguments={
                "x-message-ttl": 2000,
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": queue_name,
            },
        )

        self.retry_queue_4s = RabbitQueue(
            name=f"{retry_queue_name}_4s",
            durable=True,
            arguments={
                "x-message-ttl": 4000,
                "x-dead-letter-exchange": "",
                "x-dead-letter-routing-key": queue_name,
            },
        )

        self.dlq = RabbitQueue(
            name=dlq_name,
            durable=True,
        )

    def register_handler(self, handler: Any) -> None:
        """Register a handler with manual message acknowledgement."""

        self.broker.subscriber(
            self.queue,
            ack_policy=AckPolicy.MANUAL,
        )(handler)

    async def start(self) -> None:
        """Declare auxiliary queues before starting consumption."""

        try:
            await self.broker.connect()

            await self.broker.declare_queue(self.retry_queue_2s)
            await self.broker.declare_queue(self.retry_queue_4s)
            await self.broker.declare_queue(self.dlq)

            await self.broker.start()

        except Exception:
            await self.broker.stop()
            raise

    async def stop(self) -> None:
        """Stop the RabbitMQ broker."""

        await self.broker.stop()

    async def publish_retry(
        self,
        message: dict[str, Any],
        retry_count: int,
        message_id: str | None,
        correlation_id: str | None,
    ) -> None:
        """Publish a failed message to the appropriate retry queue."""

        if retry_count == 1:
            retry_queue = self.retry_queue_2s
        elif retry_count == 2:
            retry_queue = self.retry_queue_4s
        else:
            raise ValueError("Retry count must be 1 or 2.")

        await self.broker.publish(
            message=message,
            queue=retry_queue,
            headers={"x-retry-count": retry_count},
            message_id=message_id,
            correlation_id=correlation_id,
            persist=True,
            mandatory=True,
        )

    async def publish_to_dlq(
        self,
        message: dict[str, Any],
        retry_count: int,
        error: str,
        message_id: str | None,
        correlation_id: str | None,
    ) -> None:
        """Publish a message to the dead-letter queue."""

        await self.broker.publish(
            message=message,
            queue=self.dlq,
            headers={
                "x-retry-count": retry_count,
                "x-final-error": error[:1000],
            },
            message_id=message_id,
            correlation_id=correlation_id,
            persist=True,
            mandatory=True,
        )
