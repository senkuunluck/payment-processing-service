import asyncio
import logging

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.messaging.payment_event_handler import create_payment_event_handler
from app.messaging.rabbit_consumer import RabbitMQConsumer
from app.messaging.webhook_sender import WebhookSender
from app.services.payment_processor import PaymentProcessor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


async def run_consumer() -> None:
    settings = get_settings()
    rabbit_url = settings.rabbitmq_url.get_secret_value()

    consumer = RabbitMQConsumer(
        url=rabbit_url,
        queue_name=settings.payment_queue_name,
    )

    processor = PaymentProcessor(
        session_factory=async_session_factory,
    )

    webhook_sender = WebhookSender(timeout=10.0)

    handler = create_payment_event_handler(
        processor=processor,
        consumer=consumer,
        webhook_sender=webhook_sender,
    )

    consumer.register_handler(handler)

    try:
        await consumer.start()
        logger.info(
            "Payment consumer started. Queue: %s",
            settings.payment_queue_name,
        )

        await asyncio.Event().wait()

    finally:
        await consumer.stop()
        logger.info("Payment consumer stopped.")


if __name__ == "__main__":
    try:
        asyncio.run(run_consumer())
    except KeyboardInterrupt:
        logger.info("Consumer interrupted.")
