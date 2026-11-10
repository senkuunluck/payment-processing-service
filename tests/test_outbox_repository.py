from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.outbox import Outbox
from app.repositories.outbox import OutboxRepository


@pytest.mark.asyncio
async def test_get_unpublished_returns_only_unpublished_events(
    db_session: AsyncSession,
) -> None:
    """Return only events that have not been published."""

    repository = OutboxRepository(db_session)

    unpublished_event = Outbox(
        event_type="payment.created",
        payload={"payment_id": "payment-1"},
    )
    published_event = Outbox(
        event_type="payment.created",
        payload={"payment_id": "payment-2"},
        published_at=datetime.now(UTC),
    )

    db_session.add_all([unpublished_event, published_event])
    await db_session.flush()

    result = await repository.get_unpublished()

    assert len(result) == 1
    assert result[0].id == unpublished_event.id


@pytest.mark.asyncio
async def test_get_unpublished_respects_limit(
    db_session: AsyncSession,
) -> None:
    """Return no more events than the specified limit."""

    repository = OutboxRepository(db_session)

    base_time = datetime.now(UTC)

    events = [
        Outbox(
            event_type="payment.created",
            payload={"payment_id": f"payment-{index}"},
            created_at=base_time + timedelta(seconds=index),
        )
        for index in range(3)
    ]

    db_session.add_all(events)
    await db_session.flush()

    result = await repository.get_unpublished(limit=2)

    assert len(result) == 2
    assert result[0].id == events[0].id
    assert result[1].id == events[1].id


@pytest.mark.asyncio
async def test_get_unpublished_rejects_invalid_limit(
    db_session: AsyncSession,
) -> None:
    """Reject a limit less than one."""

    repository = OutboxRepository(db_session)

    with pytest.raises(ValueError, match="Limit must be greater than zero"):
        await repository.get_unpublished(limit=0)


@pytest.mark.asyncio
async def test_mark_as_published(
    db_session: AsyncSession,
) -> None:
    """Set published_at after successful publishing."""

    repository = OutboxRepository(db_session)

    event = Outbox(
        event_type="payment.created",
        payload={"payment_id": "payment-1"},
    )

    db_session.add(event)
    await db_session.flush()

    assert event.published_at is None

    await repository.mark_as_published(event)

    assert event.published_at is not None


@pytest.mark.asyncio
async def test_record_failure(
    db_session: AsyncSession,
) -> None:
    """Increment attempts and save the last error."""

    repository = OutboxRepository(db_session)

    event = Outbox(
        event_type="payment.created",
        payload={"payment_id": "payment-1"},
    )

    db_session.add(event)
    await db_session.flush()

    await repository.record_failure(event, "Connection timeout")

    assert event.attempts == 1
    assert event.last_error == "Connection timeout"
