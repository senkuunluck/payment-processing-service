import json
from collections.abc import AsyncGenerator
from uuid import uuid4

import aio_pika
import pytest
import pytest_asyncio

from app.core.config import get_settings
from app.messaging.rabbit_publisher import RabbitMQPublisher


@pytest_asyncio.fixture
async def rabbit_publisher() -> AsyncGenerator[tuple[RabbitMQPublisher, str], None]:
    """Provide a connected RabbitMQ publisher with an isolated queue."""
    settings = get_settings()
    queue_name = f"test_payment_events_{uuid4().hex}"

    publisher = RabbitMQPublisher(
        url=settings.rabbitmq_url.get_secret_value(),
        queue_name=queue_name,
    )

    await publisher.start()

    try:
        yield publisher, queue_name
    finally:
        await publisher.stop()


@pytest.mark.asyncio
async def test_start_declares_queue(
    rabbit_publisher: tuple[RabbitMQPublisher, str],
) -> None:
    """Verify that the publisher declares a durable queue."""
    _, queue_name = rabbit_publisher

    settings = get_settings()
    connection = await aio_pika.connect_robust(settings.rabbitmq_url.get_secret_value())

    try:
        channel = await connection.channel()
        queue = await channel.declare_queue(
            queue_name,
            durable=True,
        )
        assert queue.name == queue_name
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_publish_message(
    rabbit_publisher: tuple[RabbitMQPublisher, str],
) -> None:
    """Verify that a message is delivered to RabbitMQ."""
    publisher, queue_name = rabbit_publisher

    event_type = "payment.created"
    payload = {
        "payment_id": "test-payment-123",
        "amount": "1500.00",
        "currency": "RUB",
    }

    await publisher.publish(event_type, payload)

    settings = get_settings()
    connection = await aio_pika.connect_robust(settings.rabbitmq_url.get_secret_value())

    try:
        channel = await connection.channel()
        queue = await channel.declare_queue(
            queue_name,
            durable=True,
        )

        message = await queue.get(timeout=5, fail=False)

        assert message is not None

        async with message.process():
            received_data = json.loads(message.body)

            assert received_data["event_type"] == event_type
            assert received_data["payload"] == payload
    finally:
        await connection.close()


@pytest.mark.asyncio
async def test_publish_before_start_raises_error() -> None:
    """Verify that publishing before start is prohibited."""
    settings = get_settings()

    publisher = RabbitMQPublisher(
        url=settings.rabbitmq_url.get_secret_value(),
    )

    with pytest.raises(RuntimeError, match="must be started"):
        await publisher.publish(
            "payment.created",
            {"payment_id": "test-123"},
        )
