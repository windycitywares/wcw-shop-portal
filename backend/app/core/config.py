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
    # Serve MEDIA_ROOT from the API at /media (development and tests only; in production the media subdomain serves it).
    media_serve: bool = False
    max_photo_bytes: int = 15 * 1024 * 1024

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
    mail_reply_to: str | None = None  # where customers' replies go; empty: the from address
    contact_to: str | None = None  # inbox for contact-form messages

    # Cloudflare Turnstile (CAPTCHA). The site key is public; the secret stays on the server.
    # Without a secret, CAPTCHA checks are skipped (development only — required in production).
    turnstile_site_key: str | None = None
    turnstile_secret: str | None = None
    # Hostnames a token may come from (checked against siteverify's `hostname`). Empty = not checked
    # (development / Cloudflare test keys). Never list localhost in production.
    turnstile_hostnames: list[str] = []

    password_reset_minutes: int = 60
    max_addresses_per_user: int = 10

    # Card payments through Stripe Checkout. Both stay on the server (backend/.env). Without a secret key,
    # checkout offers only the no-charge test payment, and only outside production (or in Test mode).
    stripe_secret_key: str | None = None
    stripe_webhook_secret: str | None = None
    # Used instead of the two above while Admin → Test mode is on (Stripe "test mode" keys: no real charges).
    stripe_test_secret_key: str | None = None
    stripe_test_webhook_secret: str | None = None
    stripe_api_base: str = "https://api.stripe.com"

    # Database backups to a private GitHub repository (Admin → Backups). The token needs Contents: read and write on
    # that repository only; keep a copy of the passphrase somewhere safe: without it the backups can't be opened.
    backup_github_token: str | None = None
    backup_passphrase: str | None = None
    backup_pg_dump: str = "pg_dump"
    backup_pg_restore: str | None = None  # default: pg_restore next to pg_dump

    # Admin → Deployments: where the server keeps the checkout, the two Node apps and the deploy log.
    deploy_repo_dir: str = str(BACKEND_DIR.parent)
    storefront_app_dir: str = str(Path.home() / "apps" / "wcw-storefront")
    main_site_app_dir: str = str(Path.home() / "apps" / "wcw-main" / "site")
    deploy_github_repo: str = "windycitywares/wcw-shop-portal"  # where Admin → Deployments links pull requests
    deploy_log: str = str(Path.home() / "logs" / "wcw-deploy.log")

    # Analytics ignores crawlers and headless browsers; the browser tests turn this on.
    analytics_accept_bots: bool = False

    # CRM sync (docs/CRM_SYNC.md): changes to customers, orders and newsletter consent are posted, signed, to the
    # CRM. Off while either is unset. The secret is generated in the CRM (Administration → Integrations).
    crm_webhook_url: str | None = None  # https://crm-api.windycitywares.com/api/v1/integrations/shop/webhook
    crm_webhook_secret: str | None = None
    # Lets the CRM read customers, orders and newsletter consent (backfill, order history): a long random value
    # also saved in CRM → Administration → Integrations → Shop API token. Unset = the read API answers 404.
    crm_api_token: str | None = None

    @property
    def crm_sync_enabled(self) -> bool:
        return bool(self.crm_webhook_url and self.crm_webhook_secret)

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
