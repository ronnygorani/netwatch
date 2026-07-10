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
