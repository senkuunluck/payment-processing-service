import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings


async def main() -> None:
    """Check PostgreSQL connection."""

    settings = get_settings()

    engine = create_async_engine(
        settings.database_url,
        echo=True,
        pool_pre_ping=True,
    )

    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text("SELECT version()")
            )

            print("PostgreSQL connection successful!")
            print(result.scalar_one())

    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())