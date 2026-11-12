"""Tools for the action log. Without `mails:read` the `Message-ID`s and any mail titles in the details are masked."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import FastAPI
from mcp.server.mcpserver.exceptions import ToolError

from ..db import mail_events
from ..db.models import EventKind
from ..server.api import log as log_api
from .context import db_session, has_scope
from .redact import mask_message_id, redact
from .scoped import ScopedServer
from .scopes import Scope


def entry_json(entry: log_api.LogEntry) -> dict[str, Any]:
    data = entry.model_dump(mode="json")
    if not has_scope(Scope.mails_read):
        data["message_id"] = mask_message_id(data["message_id"])
        data["detail"] = redact(data["detail"])
    # end if
    return data
# end def


def parse_kinds(kinds: list[str] | None) -> list[EventKind]:
    try:
        return [EventKind(kind) for kind in kinds or []]
    except ValueError as e:
        raise ToolError(f"kinds must be among {', '.join(kind.value for kind in EventKind)}.") from e
    # end try
# end def


def register(server: ScopedServer, app: FastAPI) -> None:
    @server.scoped_tool(
        Scope.events_read,
        description="The action log, newest first. Filters: account_id, folder, kinds (first_seen, rule_match, action, user_action), rule, "
        "since / until (ISO times), q (text search). Pass back `next` as `before` for the following page.",
    )
    async def list_events(
        account_id: UUID | None = None, folder: str | None = None, kinds: list[str] | None = None, rule: str | None = None,
        since: datetime | None = None, until: datetime | None = None, q: str | None = None, before: str | None = None, limit: int = 50,
    ) -> dict[str, Any]:
        limit = max(1, min(limit, 200))
        async with db_session(app) as session:
            events = await mail_events.list_log(
                session, account_id=account_id, folder=folder, kinds=parse_kinds(kinds), rule=rule, since=since, until=until, text=q,
                before=None if before is None else log_api.parse_cursor(before), limit=limit + 1,
            )
        # end with
        page = events[:limit]
        return {
            "items": [entry_json(log_api.to_entry(event)) for event in page],
            "next": log_api.cursor_of(page[-1]) if len(events) > limit else None,
        }
    # end def

    @server.scoped_tool(
        Scope.events_delete,
        description="Deletes log entries: the ones the filters select, or ALL of them when no filter is given. Returns how many.",
    )
    async def clear_events(
        account_id: UUID | None = None, folder: str | None = None, kinds: list[str] | None = None, rule: str | None = None,
        since: datetime | None = None, until: datetime | None = None, q: str | None = None,
    ) -> dict[str, int]:
        async with db_session(app) as session:
            deleted = await mail_events.delete_log(
                session, account_id=account_id, folder=folder, kinds=parse_kinds(kinds), rule=rule, since=since, until=until, text=q
            )
        # end with
        return {"deleted": deleted}
    # end def
# end def
