"""Server configuration, read from the environment and `.env`."""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from ..db.engine import DEFAULT_DATABASE_URL


class ServerSettings(BaseSettings):
    """Separate from `ImapSettings`, so the server starts without any IMAP credentials.

    A set `RULES_PATH` (the variable the watcher uses) means the rules live in that file, otherwise in the database.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False)

    rules_path: Path | None = Field(default=None, description="Rules file; when unset the rules live in the database.")
    database_url: str = Field(default=DEFAULT_DATABASE_URL, description="Any async SQLAlchemy URL.")
    secret_key: SecretStr | None = Field(default=None, description="Fernet key that encrypts the account passwords.")
    server_host: str = "127.0.0.1"
    server_port: int = Field(default=8000, ge=1, le=65535)
    watch_enabled: bool = Field(default=True, description="Run the rules in the background and write the action log of each mail.")
    actions_enabled: bool = Field(
        default=False,
        description="Apply the actions of matching rules to the mailboxes. Off, the server only logs matches and the dry run shows what would happen.",
    )
    frontend_dist: Path = Field(default=Path("frontend/dist"), description="Built editor; served at `/` when the folder exists.")
    sentry_dsn: str = Field(default="", description="Backend DSN of Sentry or Bugsink; empty disables the reporting.")
    sentry_environment: str = Field(default="", description="Environment tag of the events, e.g. `production`.")
    sentry_release: str = Field(default="", description="Release of the events; defaults to the commit (`SOURCE_COMMIT`, else git).")
    sentry_traces_sample_rate: float = Field(default=0, ge=0, le=1, description="Share of the requests that get a tracing span; 0 disables tracing.")
    vite_sentry_dsn: str = Field(
        default="",
        description="Frontend DSN, usually another project than the backend's. Handed to the browser at runtime by `/api/public/client-config`, despite the name no build is involved.",
    )
    vite_sentry_environment: str = Field(default="", description="Frontend environment tag; falls back to `SENTRY_ENVIRONMENT`.")
    vite_sentry_release: str = Field(default="", description="Frontend release; falls back to the backend's release.")
    vite_sentry_traces_sample_rate: float = Field(default=0, ge=0, le=1, description="Share of the page loads and navigations that get a tracing span.")
    source_commit: str = Field(default="", description="Commit of the deployed source, set by Coolify; the fallback for the release.")
# end class
