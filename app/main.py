import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.payments import router as payments_router
from app.core.config import get_settings
from app.db.session import async_session_factory
from app.messaging.rabbit_publisher import RabbitMQPublisher
from app.workers.outbox import OutboxWorker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(application: FastAPI) -> AsyncIterator[None]:
    rabbit_url = settings.rabbitmq_url.get_secret_value()

    rabbit_publisher = RabbitMQPublisher(
        url=rabbit_url,
        queue_name=settings.payment_queue_name,
    )

    publisher_started = False
    worker_task: asyncio.Task[None] | None = None

    try:
        await rabbit_publisher.start()
        publisher_started = True

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

        logger.info("Payment API started.")
        yield

    finally:
        if worker_task is not None:
            worker_task.cancel()

            try:
                await worker_task
            except asyncio.CancelledError:
                logger.info("Outbox worker stopped.")

        if publisher_started:
            await rabbit_publisher.stop()

        logger.info("Payment API stopped.")


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    debug=settings.debug,
    lifespan=lifespan,
)

app.include_router(
    payments_router,
    prefix="/api/v1",
)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
