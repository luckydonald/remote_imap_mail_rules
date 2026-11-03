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
# end class
