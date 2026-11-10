
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.payments import router as payments_router
from app.core.config import get_settings
from app.db.session import async_session_factory
from app.messaging.rabbit_publisher import RabbitMQPublisher
from app.workers.outbox import OutboxWorker

settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    """Manage application resources during startup and shutdown."""
    rabbit_publisher = RabbitMQPublisher(
        url=settings.rabbitmq_url.get_secret_value(),
    )
    await rabbit_publisher.start()

    worker = OutboxWorker(
        session_factory=async_session_factory,
        message_publisher=rabbit_publisher,
        settings=settings,
    )

    worker_task = asyncio.create_task(
        worker.run(),
        name="outbox-worker",
    )

    application.state.rabbit_publisher = rabbit_publisher
    application.state.outbox_worker = worker
    application.state.outbox_worker_task = worker_task

    try:
        yield
    finally:
        worker_task.cancel()

        try:
            await worker_task
        except asyncio.CancelledError:
            pass

        await rabbit_publisher.stop()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Asynchronous payment processing service",
    debug=settings.debug,
    lifespan=lifespan,
)

app.include_router(payments_router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
