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
    data_dir: Path = Field(default=Path("data"), description="Everything the server stores besides the database: the rules mirror and the git credentials. The container sets `/data`.")
    rules_dir: Path | None = Field(default=None, description="Folder of the rules YAML that git tracks; defaults to `DATA_DIR/rules`. With `RULES_PATH` set, that file's folder is used instead.")
    database_url: str = Field(default=DEFAULT_DATABASE_URL, description="Any async SQLAlchemy URL.")
    secret_key: SecretStr | None = Field(default=None, description="Fernet key that encrypts the account passwords.")
    admin_username: str | None = Field(default=None, description="Login of the one admin; without it and the password nobody can log in.")
    admin_password: SecretStr | None = Field(default=None, description="Password of the admin. On Coolify this is `SERVICE_PASSWORD_ADMIN`.")
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

    @property
    def git_dir(self) -> Path:
        """The folder under git: the folder of the rules file in file mode, else the rules mirror."""
        if self.rules_path:
            return self.rules_path.resolve().parent
        # end if
        return self.rules_dir or self.data_dir / "rules"
    # end def

    @property
    def git_state_dir(self) -> Path:
        """Askpass helper and SSH key; outside the tracked folder, so they are never committed."""
        return self.data_dir / "git"
    # end def
# end class
