"""Runs the Alembic migrations."""

import asyncio
from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[3]


def make_config(database_url: str) -> Config:
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    return config
# end def


def upgrade_sync(database_url: str) -> None:
    command.upgrade(make_config(database_url), "head")
# end def


async def upgrade(database_url: str) -> None:
    """`env.py` runs its own event loop, so this must not run in ours."""
    await asyncio.to_thread(upgrade_sync, database_url)
# end def
