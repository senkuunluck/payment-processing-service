import asyncio

import asyncpg

from app.core.config import get_settings


async def main() -> None:
    url = get_settings().database_url

    connection = await asyncpg.connect(
        dsn=url.replace("postgresql+asyncpg://", "postgresql://"),
        timeout=10,
    )

    try:
        version = await connection.fetchval("SELECT version()")
        print("Direct asyncpg connection successful!")
        print(version)
    finally:
        await connection.close()


if __name__ == "__main__":
    asyncio.run(main())