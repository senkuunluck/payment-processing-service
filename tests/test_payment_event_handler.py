from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.messaging.payment_event_handler import create_payment_event_handler
from app.messaging.rabbit_consumer import RabbitMQConsumer
from app.messaging.webhook_sender import WebhookSender
from app.models.payment import PaymentCurrency, PaymentStatus
from app.schemas.payment_result import PaymentProcessingResult
from app.services.payment_processor import PaymentProcessor


def make_message() -> dict:
    return {
        "event_type": "payment.created",
        "payload": {
            "event_id": str(uuid4()),
            "payment_id": str(uuid4()),
            "amount": "100.00",
            "currency": "RUB",
            "status": "pending",
        },
    }


def make_rabbit_message(retry_count: int = 0) -> MagicMock:
    rabbit_message = MagicMock()
    rabbit_message.headers = {"x-retry-count": retry_count} if retry_count else {}
    rabbit_message.message_id = "test-message-id"
    rabbit_message.correlation_id = "test-correlation-id"
    rabbit_message.ack = AsyncMock()
    rabbit_message.nack = AsyncMock()
    return rabbit_message


@pytest.fixture
def processor() -> MagicMock:
    result = MagicMock(spec=PaymentProcessor)
    result.process = AsyncMock(
        return_value=PaymentProcessingResult(
            payment_id=uuid4(),
            amount=Decimal("100.00"),
            currency=PaymentCurrency.RUB,
            status=PaymentStatus.SUCCEEDED,
            webhook_url="https://example.com/webhook",
        )
    )
    return result


@pytest.fixture
def consumer() -> MagicMock:
    result = MagicMock(spec=RabbitMQConsumer)
    result.publish_retry = AsyncMock()
    result.publish_to_dlq = AsyncMock()
    return result


@pytest.fixture
def webhook_sender() -> MagicMock:
    result = MagicMock(spec=WebhookSender)
    result.send = AsyncMock()
    return result


@pytest.mark.asyncio
async def test_successful_processing_acknowledges_message(
    processor: MagicMock,
    consumer: MagicMock,
    webhook_sender: MagicMock,
) -> None:
    handler = create_payment_event_handler(processor, consumer, webhook_sender)
    rabbit_message = make_rabbit_message()
    message = make_message()

    await handler(message, rabbit_message)

    processor.process.assert_awaited_once()
    webhook_sender.send.assert_awaited_once()
    rabbit_message.ack.assert_awaited_once()
    rabbit_message.nack.assert_not_awaited()
    consumer.publish_retry.assert_not_awaited()
    consumer.publish_to_dlq.assert_not_awaited()


@pytest.mark.asyncio
async def test_processing_error_schedules_retry(
    processor: MagicMock,
    consumer: MagicMock,
    webhook_sender: MagicMock,
) -> None:
    processor.process.side_effect = RuntimeError("Temporary database error")
    handler = create_payment_event_handler(processor, consumer, webhook_sender)
    rabbit_message = make_rabbit_message()
    message = make_message()

    await handler(message, rabbit_message)

    consumer.publish_retry.assert_awaited_once_with(
        message=message,
        retry_count=1,
        message_id="test-message-id",
        correlation_id="test-correlation-id",
    )
    rabbit_message.ack.assert_awaited_once()
    rabbit_message.nack.assert_not_awaited()
    consumer.publish_to_dlq.assert_not_awaited()
    webhook_sender.send.assert_not_awaited()


@pytest.mark.asyncio
async def test_webhook_error_schedules_retry(
    processor: MagicMock,
    consumer: MagicMock,
    webhook_sender: MagicMock,
) -> None:
    webhook_sender.send.side_effect = RuntimeError("Webhook unavailable")
    handler = create_payment_event_handler(processor, consumer, webhook_sender)
    rabbit_message = make_rabbit_message()
    message = make_message()

    await handler(message, rabbit_message)

    processor.process.assert_awaited_once()
    webhook_sender.send.assert_awaited_once()
    consumer.publish_retry.assert_awaited_once()
    rabbit_message.ack.assert_awaited_once()


@pytest.mark.asyncio
async def test_third_failed_attempt_sends_message_to_dlq(
    processor: MagicMock,
    consumer: MagicMock,
    webhook_sender: MagicMock,
) -> None:
    webhook_sender.send.side_effect = RuntimeError("Webhook permanently unavailable")
    handler = create_payment_event_handler(processor, consumer, webhook_sender)
    rabbit_message = make_rabbit_message(retry_count=2)
    message = make_message()

    await handler(message, rabbit_message)

    consumer.publish_to_dlq.assert_awaited_once_with(
        message=message,
        retry_count=3,
        error="Webhook permanently unavailable",
        message_id="test-message-id",
        correlation_id="test-correlation-id",
    )
    consumer.publish_retry.assert_not_awaited()
    rabbit_message.ack.assert_awaited_once()
    rabbit_message.nack.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_retry_publication_requeues_original_message(
    processor: MagicMock,
    consumer: MagicMock,
    webhook_sender: MagicMock,
) -> None:
    processor.process.side_effect = RuntimeError("Temporary error")
    consumer.publish_retry.side_effect = RuntimeError("RabbitMQ unavailable")
    handler = create_payment_event_handler(processor, consumer, webhook_sender)
    rabbit_message = make_rabbit_message()

    await handler(make_message(), rabbit_message)

    rabbit_message.nack.assert_awaited_once_with(requeue=True)
    rabbit_message.ack.assert_not_awaited()


@pytest.mark.asyncio
async def test_failed_dlq_publication_requeues_original_message(
    processor: MagicMock,
    consumer: MagicMock,
    webhook_sender: MagicMock,
) -> None:
    processor.process.side_effect = RuntimeError("Processing failed")
    consumer.publish_to_dlq.side_effect = RuntimeError("RabbitMQ unavailable")
    handler = create_payment_event_handler(processor, consumer, webhook_sender)
    rabbit_message = make_rabbit_message(retry_count=2)

    await handler(make_message(), rabbit_message)

    rabbit_message.nack.assert_awaited_once_with(requeue=True)
    rabbit_message.ack.assert_not_awaited()


@pytest.mark.asyncio
async def test_invalid_event_is_retried(
    processor: MagicMock,
    consumer: MagicMock,
    webhook_sender: MagicMock,
) -> None:
    handler = create_payment_event_handler(processor, consumer, webhook_sender)
    rabbit_message = make_rabbit_message()

    await handler({"invalid": "event"}, rabbit_message)

    processor.process.assert_not_awaited()
    webhook_sender.send.assert_not_awaited()
    consumer.publish_retry.assert_awaited_once()
    rabbit_message.ack.assert_awaited_once()
