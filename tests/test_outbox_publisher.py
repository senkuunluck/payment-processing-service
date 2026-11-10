import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox import Outbox
from app.services.outbox_publisher import OutboxPublisher
from tests.fakes import FakeMessagePublisher


@pytest.mark.asyncio
async def test_publish_batch_success(
    db_session: AsyncSession,
) -> None:
    """Publish all unpublished events successfully."""

    events = [
        Outbox(
            event_type="payment.created",
            payload={"payment_id": f"payment-{index}"},
        )
        for index in range(3)
    ]

    db_session.add_all(events)
    await db_session.flush()

    fake_publisher = FakeMessagePublisher()
    publisher = OutboxPublisher(db_session, fake_publisher)

    result = await publisher.publish_batch()

    assert result == 3
    assert len(fake_publisher.published_messages) == 3

    for event in events:
        assert event.published_at is not None
        assert event.attempts == 0


@pytest.mark.asyncio
async def test_publish_batch_handles_failure(
    db_session: AsyncSession,
) -> None:
    """Continue publishing other events after a failure."""

    events = [
        Outbox(
            event_type="payment.created",
            payload={"payment_id": "payment-1"},
        ),
        Outbox(
            event_type="payment.failed",
            payload={"payment_id": "payment-2"},
        ),
    ]

    db_session.add_all(events)
    await db_session.flush()

    fake_publisher = FakeMessagePublisher()
    fake_publisher.fail_event_types.add("payment.failed")

    publisher = OutboxPublisher(db_session, fake_publisher)

    result = await publisher.publish_batch()

    assert result == 1
    assert len(fake_publisher.published_messages) == 1

    assert events[0].published_at is not None
    assert events[0].attempts == 0

    assert events[1].published_at is None
    assert events[1].attempts == 1
    assert events[1].last_error == "Simulated broker connection error"


@pytest.mark.asyncio
async def test_publish_batch_respects_batch_size(
    db_session: AsyncSession,
) -> None:
    """Publish no more events than the specified batch size."""

    events = [
        Outbox(
            event_type="payment.created",
            payload={"payment_id": f"payment-{index}"},
        )
        for index in range(3)
    ]

    db_session.add_all(events)
    await db_session.flush()

    fake_publisher = FakeMessagePublisher()
    publisher = OutboxPublisher(db_session, fake_publisher)

    result = await publisher.publish_batch(batch_size=2)

    assert result == 2
    assert len(fake_publisher.published_messages) == 2


@pytest.mark.asyncio
async def test_publish_batch_rejects_invalid_batch_size(
    db_session: AsyncSession,
) -> None:
    """Reject a batch size less than one."""

    fake_publisher = FakeMessagePublisher()
    publisher = OutboxPublisher(db_session, fake_publisher)

    with pytest.raises(ValueError, match="Batch size must be greater than zero"):
        await publisher.publish_batch(batch_size=0)
