"""What the server holds and how busy it is, mounted at `/api/stats`. A snapshot, nothing is kept."""

import asyncio
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import mail_events
from ...db.models import Account, EventKind, McpToken, Rule, Template
from ..sentry import release_of
from ..settings import ServerSettings
from ..watcher import Watcher
from .accounts import get_session

router = APIRouter()


class DatabaseStats(BaseModel):
    dialect: str
    size_bytes: int | None
    """The SQLite file with its write-ahead log; `None` for other databases and in-memory ones."""


class TableCounts(BaseModel):
    accounts: int
    rules: int
    templates: int
    mcp_tokens: int
    mail_events: int
    mail_events_by_kind: dict[str, int]


class WatcherStats(BaseModel):
    enabled: bool
    actions_enabled: bool
    folders: int
    """Folders the watcher has scheduled or is waiting on; empty until the first check after a start."""
    jobs: int


class Stats(BaseModel):
    database: DatabaseStats
    tables: TableCounts
    first_event: datetime | None
    last_event: datetime | None
    data_dir_bytes: int
    watcher: WatcherStats
    started_at: datetime
    release: str


def sqlite_size(database_url: str) -> int | None:
    """Size of the SQLite file and its `-wal`, `None` when the URL is not a SQLite file."""
    url = make_url(database_url)
    if not url.get_backend_name() == "sqlite" or not url.database or url.database == ":memory:":
        return None
    # end if
    path = Path(url.database)
    return sum(candidate.stat().st_size for candidate in (path, path.with_name(path.name + "-wal")) if candidate.is_file())
# end def


def folder_size(path: Path) -> int:
    """All file sizes below `path`; files that vanish while walking count as 0."""
    total = 0
    for file in path.rglob("*"):
        try:
            if file.is_file() and not file.is_symlink():
                total += file.stat().st_size
            # end if
        except OSError:
            continue
        # end try
    # end for
    return total
# end def


async def count(session: AsyncSession, model: type) -> int:
    return await session.scalar(select(func.count()).select_from(model)) or 0
# end def


@router.get("")
async def get_stats(request: Request, session: AsyncSession = Depends(get_session)) -> Stats:
    settings: ServerSettings = request.app.state.settings
    watcher: Watcher = request.app.state.watcher
    by_kind = await mail_events.count_by_kind(session)
    return Stats(
        database=DatabaseStats(dialect=make_url(settings.database_url).get_backend_name(), size_bytes=await asyncio.to_thread(sqlite_size, settings.database_url)),
        tables=TableCounts(
            accounts=await count(session, Account), rules=await count(session, Rule), templates=await count(session, Template),
            mcp_tokens=await count(session, McpToken), mail_events=sum(by_kind.values()), mail_events_by_kind=by_kind,
        ),
        first_event=await mail_events.first_event_at(session),
        last_event=await mail_events.last_event_at(session, tuple(EventKind)),
        data_dir_bytes=await asyncio.to_thread(folder_size, settings.data_dir),
        watcher=WatcherStats(enabled=watcher.enabled, actions_enabled=watcher.actions_enabled, folders=len(watcher.due), jobs=len(watcher.working_jobs())),
        started_at=request.app.state.started_at,
        release=await asyncio.to_thread(release_of, settings),
    )
# end def
