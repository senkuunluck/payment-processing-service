from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "Payment Processing Service"
    app_version: str = "0.1.0"
    debug: bool = False

    api_key: str = "development-secret-key"

    database_url: str = (
        "postgresql+asyncpg://payment_user:payment_password@127.0.0.1:5433/payment_service"
    )

    payment_queue_name: str = "payments.new"

    rabbitmq_url: SecretStr = SecretStr("amqp://payment_user:payment_password@localhost:5672/")
    outbox_poll_interval: float = 2.0
    outbox_batch_size: int = 100


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
