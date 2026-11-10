from typing import Any

from faststream.rabbit import RabbitBroker, RabbitQueue


class RabbitMQPublisher:
    """Publish messages to RabbitMQ using FastStream."""

    def __init__(
        self,
        url: str,
        queue_name: str = "payment_events",
    ) -> None:
        self.broker = RabbitBroker(url)
        self.queue = RabbitQueue(
            name=queue_name,
            durable=True,
        )
        self._started = False

    async def start(self) -> None:
        """Start the broker connection and declare the queue."""
        if self._started:
            return

        await self.broker.start()
        await self.broker.declare_queue(self.queue)
        self._started = True

    async def stop(self) -> None:
        """Stop the broker connection."""
        if not self._started:
            return

        await self.broker.stop()
        self._started = False

    async def publish(
        self,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Publish an event to the payment events queue."""
        if not self._started:
            raise RuntimeError("RabbitMQPublisher must be started before publishing.")

        await self.broker.publish(
            message={
                "event_type": event_type,
                "payload": payload,
            },
            queue=self.queue,
            persist=True,
            mandatory=True,
        )
