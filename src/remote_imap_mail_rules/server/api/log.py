"""The action log across all mails, mounted at `/api/log`."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import mail_events
from ...db.mail_events import as_utc
from ...db.models import EventKind, MailEvent
from ..watcher import Watcher
from .accounts import get_session

router = APIRouter()

CHANGE_KINDS = (EventKind.first_seen, EventKind.rule_match, EventKind.user_action)
"""What counts as the watcher having found a change."""


class LogEntry(BaseModel):
    id: UUID
    account_id: UUID
    folder: str
    uid: int
    message_id: str | None
    kind: str
    rule_name: str | None
    detail: dict[str, Any]
    created_at: datetime
# end class


class LogPage(BaseModel):
    items: list[LogEntry]
    next: str | None
    """Pass as `before` to get the following page; `None` on the last one."""
# end class


class LogJob(BaseModel):
    kind: str
    """`folder` (being checked) or `actions` (rules running over one mail)."""
    account_id: UUID
    folder: str
    uid: int | None
    started_at: datetime
# end class


class LogStatus(BaseModel):
    watcher_enabled: bool
    last_run: datetime | None
    """In memory only, so `None` after a restart until the watching wakes up the first time."""
    next_run: datetime | None
    """The earliest planned poll, `None` when every folder waits for a server push or nothing is scheduled yet. In memory only."""
    push: bool
    """Some folder waits for a server push (`IDLE`), so it also wakes up without a planned time."""
    last_change: datetime | None
    last_action: datetime | None
    jobs: list[LogJob]
    """What the watcher is busy with right now, oldest first. In memory only."""
# end class


def to_entry(event: MailEvent) -> LogEntry:
    return LogEntry(
        id=event.id, account_id=event.account_id, folder=event.folder, uid=event.uid, message_id=event.message_id, kind=event.kind,
        rule_name=event.rule_name, detail=event.detail, created_at=as_utc(event.created_at),
    )
# end def


def cursor_of(event: MailEvent) -> str:
    return f"{as_utc(event.created_at).isoformat()}|{event.id}"
# end def


def parse_cursor(value: str) -> tuple[datetime, UUID]:
    try:
        created, event_id = value.split("|", 1)
        return datetime.fromisoformat(created), UUID(event_id)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=["The cursor is not valid."]) from error
    # end try
# end def


@router.get("/events")
async def list_log(
    account_id: UUID | None = None,
    folder: str | None = None,
    kind: list[EventKind] = Query(default=[]),
    rule: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    q: str | None = None,
    before: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    session: AsyncSession = Depends(get_session),
) -> LogPage:
    """Newest first; `q` searches the rule name, folder, `Message-ID` and the detail, ignoring case."""
    events = await mail_events.list_log(
        session, account_id=account_id, folder=folder, kinds=kind, rule=rule, since=since, until=until, text=q,
        before=None if before is None else parse_cursor(before), limit=limit + 1,
    )
    page = events[:limit]
    return LogPage(items=[to_entry(event) for event in page], next=cursor_of(page[-1]) if len(events) > limit else None)
# end def


@router.get("/status")
async def status(request: Request, session: AsyncSession = Depends(get_session)) -> LogStatus:
    """When the watcher last woke up, last found a change and last ran an action."""
    watcher: Watcher = request.app.state.watcher
    return LogStatus(
        watcher_enabled=watcher.enabled,
        last_run=watcher.last_run,
        next_run=watcher.next_run(),
        push=watcher.push_folders(),
        last_change=await mail_events.last_event_at(session, CHANGE_KINDS),
        last_action=await mail_events.last_event_at(session, (EventKind.action,)),
        jobs=[LogJob(kind=job.kind, account_id=job.account_id, folder=job.folder, uid=job.uid, started_at=job.started_at) for job in watcher.working_jobs()],
    )
# end def
