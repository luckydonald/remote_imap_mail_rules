"""Server configuration, read from the environment and `.env`."""

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseSettings):
    """Separate from `ImapSettings`, so the server starts without any IMAP credentials.

    `RULES_PATH` is the same variable the watcher uses.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False)

    rules_path: Path = Path("rules/example.yml")
    server_host: str = "127.0.0.1"
    server_port: int = Field(default=8000, ge=1, le=65535)
    frontend_dist: Path = Field(default=Path("frontend/dist"), description="Built editor; served at `/` when the folder exists.")
# end class
