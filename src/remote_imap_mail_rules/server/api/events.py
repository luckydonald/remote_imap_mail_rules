"""The action log of a mail, mounted at `/api/mail` next to the mail browser."""

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import mail_events
from ...db.models import MailEvent
from .accounts import get_session

router = APIRouter()


class EventOut(BaseModel):
    id: UUID
    kind: str
    rule_name: str | None
    detail: dict[str, Any]
    created_at: datetime
# end class


def to_out(event: MailEvent) -> EventOut:
    return EventOut(id=event.id, kind=event.kind, rule_name=event.rule_name, detail=event.detail, created_at=event.created_at)
# end def


@router.get("/accounts/{account_id}/messages/{uid}/events")
async def list_events(account_id: UUID, uid: int, folder: str = Query("INBOX"), session: AsyncSession = Depends(get_session)) -> list[EventOut]:
    """The log of one mail, oldest first. Empty when nothing was logged, e.g. because the watcher is off."""
    return [to_out(event) for event in await mail_events.list_events(session, account_id, folder, uid)]
# end def
