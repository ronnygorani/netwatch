from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven configuration. DB credentials are split into
    individual fields so each can be rotated independently in a secrets manager."""

    # Database
    postgres_user: str = "netwatch"
    postgres_password: str = "changeme"
    postgres_db: str = "netwatch"
    postgres_host: str = "db"
    postgres_port: int = 5432

    # API server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    log_level: str = "info"

    # Runtime context
    environment: str = "development"

    # Comma-separated allowed origins; "*" is dev-only.
    cors_origins: str = "*"

    # Writes per key per minute. In-memory limiter: per-process until Redis (P6).
    rate_limit_per_minute: int = 120

    # Metrics older than this are purged opportunistically; 0 disables.
    metric_retention_days: int = 30

    # Source of truth. Empty token disables SoT sync (503 from /v1/sot/sync).
    nautobot_url: str = "http://nautobot:8080"
    nautobot_token: str = ""
    # Shared secret for verifying Nautobot webhook signatures; empty disables.
    nautobot_webhook_secret: str = ""

    # Job queue broker. DB 2: Nautobot's cache and celery use 0 and 1.
    redis_url: str = "redis://redis:6379/2"

    # Device credentials for job executors (same pair the poller uses).
    netmiko_username: str = ""
    netmiko_password: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def _refuse_default_password_outside_dev(self) -> "Settings":
        """Refuse to start with the shipped default password outside dev/testing (FM-C2)."""
        if self.environment not in ("development", "testing") and (
            self.postgres_password == "changeme"
        ):
            raise ValueError(
                "POSTGRES_PASSWORD is still the default 'changeme' but "
                f"ENVIRONMENT={self.environment!r} — refusing to start. Set a real password."
            )
        return self

    @property
    def database_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # Real env vars take priority over .env values.
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
