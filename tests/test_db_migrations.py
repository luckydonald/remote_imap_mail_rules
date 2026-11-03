"""The migrations run on an empty SQLite and match the models."""

from pathlib import Path

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from remote_imap_mail_rules.db import models  # noqa: F401
from remote_imap_mail_rules.db.base import Base
from remote_imap_mail_rules.db.migrate import upgrade


async def test_upgrade_creates_tables(tmp_path: Path) -> None:
    path = tmp_path / "db.sqlite3"
    await upgrade(f"sqlite+aiosqlite:///{path}")
    engine = create_engine(f"sqlite:///{path}")
    with engine.connect() as connection:
        assert {"accounts", "mail_events", "rules", "templates"} <= set(inspect(connection).get_table_names())
        # No drift between the models and the migrations.
        assert compare_metadata(MigrationContext.configure(connection), Base.metadata) == []
    # end with
    engine.dispose()
# end def
