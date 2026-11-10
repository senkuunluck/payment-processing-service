import logging
from collections.abc import Awaitable, Callable
from typing import Any

from faststream.rabbit import RabbitMessage

from app.messaging.rabbit_consumer import RabbitMQConsumer
from app.messaging.webhook_sender import WebhookSender
from app.schemas.payment_event import PaymentEventEnvelope
from app.services.payment_processor import PaymentProcessor

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3

PaymentEventHandler = Callable[
    [dict[str, Any], RabbitMessage],
    Awaitable[None],
]


def create_payment_event_handler(
    processor: PaymentProcessor,
    consumer: RabbitMQConsumer,
    webhook_sender: WebhookSender,
) -> PaymentEventHandler:
    """Create a RabbitMQ handler for payment processing and webhooks."""

    async def handle_payment_event(
        message: dict[str, Any],
        rabbit_message: RabbitMessage,
    ) -> None:
        try:
            envelope = PaymentEventEnvelope.model_validate(message)

            result = await processor.process(envelope.payload)

            await webhook_sender.send(
                url=result.webhook_url,
                payment_id=result.payment_id,
                amount=str(result.amount),
                currency=result.currency,
                status=result.status,
                event_id=str(envelope.payload.event_id),
            )

        except Exception as exc:
            previous_retries = rabbit_message.headers.get(
                "x-retry-count",
                0,
            )

            try:
                previous_retries = int(previous_retries)
            except (TypeError, ValueError):
                previous_retries = 0

            attempts = previous_retries + 1

            logger.exception(
                "Payment event processing failed. Attempt %s/%s",
                attempts,
                MAX_ATTEMPTS,
            )

            try:
                if attempts < MAX_ATTEMPTS:
                    await consumer.publish_retry(
                        message=message,
                        retry_count=attempts,
                        message_id=rabbit_message.message_id,
                        correlation_id=rabbit_message.correlation_id,
                    )

                    logger.warning(
                        "Payment event scheduled for retry %s/%s",
                        attempts,
                        MAX_ATTEMPTS,
                    )

                else:
                    await consumer.publish_to_dlq(
                        message=message,
                        retry_count=attempts,
                        error=str(exc),
                        message_id=rabbit_message.message_id,
                        correlation_id=rabbit_message.correlation_id,
                    )

                    logger.error(
                        "Payment event moved to DLQ after %s attempts",
                        attempts,
                    )

            except Exception:
                logger.exception("Failed to publish payment event to retry/DLQ")

                await rabbit_message.nack(requeue=True)
                return

            await rabbit_message.ack()
            return

        await rabbit_message.ack()

    return handle_payment_event
