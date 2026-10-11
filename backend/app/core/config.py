"""Application settings, loaded from environment variables / .env."""

from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Windy City Wares API"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://wcw:wcw@localhost:5432/wcw"
    db_echo: bool = False
    db_use_null_pool: bool = False

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120

    cors_origins: list[str] = ["http://localhost:3000"]

    admin_email: str | None = None
    admin_password: str | None = None

    max_import_bytes: int = 20 * 1024 * 1024

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @model_validator(mode="after")
    def _check_secrets(self) -> "Settings":
        if self.is_production and self.jwt_secret == "change-me":
            raise ValueError("JWT_SECRET must be set in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
