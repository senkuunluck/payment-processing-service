from fastapi import FastAPI

from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Asynchronous payment processing service",
    debug=settings.debug,
)


@app.get("/health", tags=["Health"])
async def health_check() -> dict[str, str]:
    """Return application health status."""
    return {"status": "ok"}
