"""Application settings, loaded from environment variables and env files (see ENV_FILES)."""

import os
from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parents[2]


def _is_production() -> bool:
    env = os.environ.get("ENVIRONMENT")
    if env is None:
        try:
            for line in (BACKEND_DIR / ".env").read_text(encoding="utf-8").splitlines():
                if line.strip().startswith("ENVIRONMENT="):
                    env = line.split("=", 1)[1].strip().strip("'\"")
        except OSError:
            pass
    return (env or "").lower() == "production"


# Later files override earlier ones; real environment variables override all of them.
#   production.env — non-secret production defaults, in Git (mail server, contact inbox, site URL)
#   .env           — secrets, on the server only
#   site.env       — optional non-secret server overrides, not in Git
ENV_FILES = (
    *((BACKEND_DIR / "production.env",) if _is_production() else ()),
    BACKEND_DIR / ".env",
    BACKEND_DIR / "site.env",
)


class Settings(BaseSettings):
    # Absolute paths: the web server may start the app from a different working directory.
    model_config = SettingsConfigDict(env_file=ENV_FILES, env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Windy City Wares API"
    environment: str = "development"
    api_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://wcw:wcw@localhost:5432/wcw"
    db_echo: bool = False
    db_use_null_pool: bool = False
    db_connect_timeout: int = 10  # seconds; fail fast instead of hanging a web worker

    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 120

    cors_origins: list[str] = ["http://localhost:3000"]

    admin_email: str | None = None
    admin_password: str | None = None

    max_import_bytes: int = 20 * 1024 * 1024

    # Where product photos are stored on disk and the public URL they're served from
    # (HostItBro: /home2/windycit/media.windycitywares.com → https://media.windycitywares.com).
    media_root: str = str(BACKEND_DIR / "media")
    media_url: str = "/media"

    # Public storefront URL, used for links in emails (password reset).
    site_url: str = "http://localhost:3000"

    # Outgoing email (HostItBro mailbox, e.g. no-reply@windycitywares.com). Leave SMTP_HOST empty in
    # development: emails are then written to the log instead of being sent.
    smtp_host: str | None = None
    smtp_port: int = 465
    smtp_security: str = "ssl"  # "ssl" (port 465), "starttls" (port 587) or "none"
    smtp_user: str | None = None
    smtp_password: str | None = None
    mail_from: str = "no-reply@windycitywares.com"
    mail_from_name: str = "WindyCityWares"
    contact_to: str | None = None  # inbox for contact-form messages

    # Cloudflare Turnstile (CAPTCHA). The site key is public; the secret stays on the server.
    # Without a secret, CAPTCHA checks are skipped (development only — required in production).
    turnstile_site_key: str | None = None
    turnstile_secret: str | None = None
    # Hostnames a token may come from (checked against siteverify's `hostname`). Empty = not checked
    # (development / Cloudflare test keys). Never list localhost in production.
    turnstile_hostnames: list[str] = []

    # Stripe (hosted Checkout). Both come from the Stripe dashboard and stay in backend/.env.
    # Card payments are offered only when both are set.
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None

    password_reset_minutes: int = 60
    max_addresses_per_user: int = 10

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
