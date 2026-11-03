"""Alembic environment, async. The URL comes from the config, else `DATABASE_URL`, else the default."""

import asyncio
import os

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from remote_imap_mail_rules.db.base import Base
from remote_imap_mail_rules.db.engine import DEFAULT_DATABASE_URL
from remote_imap_mail_rules.db import models  # noqa: F401, registers the tables

config = context.config
target_metadata = Base.metadata


def get_url() -> str:
    return config.get_main_option("sqlalchemy.url") or os.environ.get("DATABASE_URL") or DEFAULT_DATABASE_URL
# end def


def do_run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()
    # end with
# end def


async def run_online() -> None:
    engine = create_async_engine(get_url())
    async with engine.connect() as connection:
        await connection.run_sync(do_run)
    # end with
    await engine.dispose()
# end def


if context.is_offline_mode():
    context.configure(url=get_url(), target_metadata=target_metadata, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()
    # end with
else:
    asyncio.run(run_online())
# end if
