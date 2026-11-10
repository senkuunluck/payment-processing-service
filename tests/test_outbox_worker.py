
from unittest.mock import AsyncMock, MagicMock

import pytest
from contextlib import asynccontextmanager
from app.core.config import Settings
from app.workers.outbox import OutboxWorker



@pytest.fixture
def worker_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[OutboxWorker, MagicMock, MagicMock, AsyncMock, MagicMock]:
    settings = Settings(
        outbox_poll_interval=2.0,
        outbox_batch_size=10,
    )
    session = AsyncMock()

    transaction_calls = MagicMock()

    @asynccontextmanager
    async def fake_begin():
        transaction_calls()
        yield

    session.begin = fake_begin

    session.begin = fake_begin

    session_context = MagicMock()
    session_context.__aenter__ = AsyncMock(return_value=session)
    session_context.__aexit__ = AsyncMock(return_value=None)

    session_factory = MagicMock(return_value=session_context)
    message_publisher = AsyncMock()

    outbox_service = MagicMock()
    outbox_service.publish_batch = AsyncMock(return_value=3)

    outbox_service_class = MagicMock(return_value=outbox_service)
    monkeypatch.setattr(
        "app.workers.outbox.OutboxPublisher",
        outbox_service_class,
    )

    worker = OutboxWorker(
        session_factory=session_factory,
        message_publisher=message_publisher,
        settings=settings,
    )

    return worker, session_factory, session, outbox_service, transaction_calls



def test_worker_initialization(
        worker_dependencies: tuple[
            OutboxWorker,
            MagicMock,
            MagicMock,
            AsyncMock,
            MagicMock,
        ],
) -> None:
    worker, _, _, _, _ = worker_dependencies

    assert worker.poll_interval == 2.0
    assert worker.batch_size == 10
    assert worker._running is False


@pytest.mark.asyncio
async def test_process_batch(
        worker_dependencies: tuple[
            OutboxWorker,
            MagicMock,
            MagicMock,
            AsyncMock,
            MagicMock,
        ],
) -> None:
    worker, session_factory, _, outbox_service, transaction_calls = worker_dependencies

    result = await worker.process_batch()

    assert result == 3
    session_factory.assert_called_once()
    transaction_calls.assert_called_once()
    outbox_service.publish_batch.assert_awaited_once_with(batch_size=10)


@pytest.mark.asyncio
async def test_process_empty_batch(
        worker_dependencies: tuple[
            OutboxWorker,
            MagicMock,
            MagicMock,
            AsyncMock,
            MagicMock,
        ],
) -> None:
    worker, _, _, outbox_service, _ = worker_dependencies
    outbox_service.publish_batch.return_value = 0

    result = await worker.process_batch()

    assert result == 0
    outbox_service.publish_batch.assert_awaited_once_with(batch_size=10)
