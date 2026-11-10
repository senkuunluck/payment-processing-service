from hmac import compare_digest
from typing import Annotated

from fastapi import Header, HTTPException, status

from app.core.config import get_settings


async def require_api_key(
    api_key: Annotated[str, Header(alias="X-API-Key")],
) -> None:
    """Validate the API key provided by the client."""

    settings = get_settings()

    if not compare_digest(api_key, settings.api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
