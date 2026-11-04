"""Account and runtime configuration, read from the environment and `.env`."""

from pathlib import Path
from uuid import UUID

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class ImapSettings(BaseSettings):
    """The one IMAP account of the PoC, shaped as a single account so multi-account later is a list of these.

    Field names equal the environment variable names, e.g. `imap_host` is read from `IMAP_HOST`.
    The automated tests subclass this with `env_prefix="TEST_"` and no `.env` file, so they never touch the real account.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False, env_ignore_empty=True)

    imap_account_id: UUID = Field(description="Immutable id that rules refer to; names can change.")
    imap_account_name: str | None = Field(default=None, description="Display label only, never used as a reference.")
    imap_host: str
    imap_port: int = Field(default=993, ge=1, le=65535)
    imap_ssl: bool = True
    imap_username: str
    imap_password: SecretStr
    imap_page_size: int = Field(default=50, ge=1, description="Mails per page when loading a folder.")
    imap_poll_interval: float = Field(default=60.0, gt=0, description="Seconds between polls when the server has no IDLE.")
    rules_path: Path = Path("rules/example.yml")
# end class
