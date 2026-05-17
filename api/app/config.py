from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration for the NetWatch API, read from environment variables.

    Split into individual fields (not a single DATABASE_URL) so each
    value can be rotated independently in a secrets manager.
    """

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

    @property
    def database_url(self) -> str:
        """Assemble the SQLAlchemy connection string from individual parts."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # pydantic-settings v2: use SettingsConfigDict instead of the inner Config class.
    # Reads from .env file; real env vars take priority (Kubernetes Secrets win).
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)


settings = Settings()
