from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import engine, get_session
from app.main import app


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provide a database session rolled back after each test."""

    async with engine.connect() as connection:
        transaction = await connection.begin()

        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            autoflush=False,
            join_transaction_mode="create_savepoint",
        )

        try:
            yield session
        finally:
            await session.close()
            await transaction.rollback()


@pytest_asyncio.fixture
async def client(
    db_session: AsyncSession,
) -> AsyncGenerator[AsyncClient, None]:
    """Provide an HTTP client using the test database session."""

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)

    try:
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as test_client:
            yield test_client
    finally:
        app.dependency_overrides.pop(get_session, None)
