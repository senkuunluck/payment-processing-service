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

    api_key: SecretStr = SecretStr("secret")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/payments"

    rabbitmq_url: SecretStr = SecretStr("amqp://guest:guest@localhost:5672/")


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
