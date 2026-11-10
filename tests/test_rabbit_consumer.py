from unittest.mock import AsyncMock, MagicMock

import pytest
from faststream import AckPolicy

from app.messaging.rabbit_consumer import RabbitMQConsumer


@pytest.fixture
def consumer() -> RabbitMQConsumer:
    return RabbitMQConsumer(
        url="amqp://guest:guest@localhost:5672/",
        queue_name="payments.new",
        retry_queue_name="test_payment_events_retry",
        dlq_name="test_payment_events_dlq",
    )


def test_consumer_configures_queues(
    consumer: RabbitMQConsumer,
) -> None:
    assert consumer.queue.name == "payments.new"
    assert consumer.queue.durable is True

    assert consumer.retry_queue_2s.name == "test_payment_events_retry_2s"
    assert consumer.retry_queue_2s.arguments == {
        "x-message-ttl": 2000,
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": "payments.new",
        "x-queue-type": "classic",
    }

    assert consumer.retry_queue_4s.name == "test_payment_events_retry_4s"
    assert consumer.retry_queue_4s.arguments == {
        "x-message-ttl": 4000,
        "x-dead-letter-exchange": "",
        "x-dead-letter-routing-key": "payments.new",
        "x-queue-type": "classic",
    }

    assert consumer.dlq.name == "test_payment_events_dlq"
    assert consumer.dlq.durable is True


def test_register_handler_uses_manual_ack(
    consumer: RabbitMQConsumer,
) -> None:
    handler = AsyncMock()
    subscriber = MagicMock()
    consumer.broker.subscriber = MagicMock(return_value=subscriber)

    consumer.register_handler(handler)

    consumer.broker.subscriber.assert_called_once_with(
        consumer.queue,
        ack_policy=AckPolicy.MANUAL,
    )
    subscriber.assert_called_once_with(handler)


@pytest.mark.asyncio
async def test_start_declares_retry_and_dlq_queues(
    consumer: RabbitMQConsumer,
) -> None:
    consumer.broker.connect = AsyncMock()
    consumer.broker.start = AsyncMock()
    consumer.broker.declare_queue = AsyncMock()

    await consumer.start()

    consumer.broker.connect.assert_awaited_once()

    assert consumer.broker.declare_queue.await_count == 3
    consumer.broker.declare_queue.assert_any_await(consumer.retry_queue_2s)
    consumer.broker.declare_queue.assert_any_await(consumer.retry_queue_4s)
    consumer.broker.declare_queue.assert_any_await(consumer.dlq)

    consumer.broker.start.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_stops_broker_if_queue_declaration_fails(
    consumer: RabbitMQConsumer,
) -> None:
    consumer.broker.connect = AsyncMock()
    consumer.broker.declare_queue = AsyncMock(side_effect=RuntimeError("Queue declaration failed"))
    consumer.broker.start = AsyncMock()
    consumer.broker.stop = AsyncMock()

    with pytest.raises(RuntimeError, match="Queue declaration failed"):
        await consumer.start()

    consumer.broker.connect.assert_awaited_once()
    consumer.broker.stop.assert_awaited_once()
    consumer.broker.start.assert_not_awaited()


@pytest.mark.asyncio
async def test_first_retry_uses_two_second_queue(
    consumer: RabbitMQConsumer,
) -> None:
    consumer.broker.publish = AsyncMock()
    message = {"event_type": "payment.created", "payload": {}}

    await consumer.publish_retry(
        message=message,
        retry_count=1,
        message_id="message-1",
        correlation_id="correlation-1",
    )

    consumer.broker.publish.assert_awaited_once_with(
        message=message,
        queue=consumer.retry_queue_2s,
        headers={"x-retry-count": 1},
        message_id="message-1",
        correlation_id="correlation-1",
        persist=True,
        mandatory=True,
    )


@pytest.mark.asyncio
async def test_second_retry_uses_four_second_queue(
    consumer: RabbitMQConsumer,
) -> None:
    consumer.broker.publish = AsyncMock()
    message = {"event_type": "payment.created", "payload": {}}

    await consumer.publish_retry(
        message=message,
        retry_count=2,
        message_id="message-1",
        correlation_id="correlation-1",
    )

    consumer.broker.publish.assert_awaited_once_with(
        message=message,
        queue=consumer.retry_queue_4s,
        headers={"x-retry-count": 2},
        message_id="message-1",
        correlation_id="correlation-1",
        persist=True,
        mandatory=True,
    )


@pytest.mark.asyncio
async def test_invalid_retry_count_is_rejected(
    consumer: RabbitMQConsumer,
) -> None:
    with pytest.raises(ValueError, match="Retry count must be 1 or 2"):
        await consumer.publish_retry(
            message={},
            retry_count=3,
            message_id="message-1",
            correlation_id="correlation-1",
        )


@pytest.mark.asyncio
async def test_publish_to_dlq_includes_error_information(
    consumer: RabbitMQConsumer,
) -> None:
    consumer.broker.publish = AsyncMock()
    message = {"event_type": "payment.created", "payload": {}}

    await consumer.publish_to_dlq(
        message=message,
        retry_count=3,
        error="Processing failed",
        message_id="message-1",
        correlation_id="correlation-1",
    )

    consumer.broker.publish.assert_awaited_once_with(
        message=message,
        queue=consumer.dlq,
        headers={
            "x-retry-count": 3,
            "x-final-error": "Processing failed",
        },
        message_id="message-1",
        correlation_id="correlation-1",
        persist=True,
        mandatory=True,
    )
