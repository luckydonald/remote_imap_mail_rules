"""Repository of the action log per mail."""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import EventKind, MailEvent


async def record_event(
    session: AsyncSession,
    account_id: UUID,
    folder: str,
    uid: int,
    kind: EventKind,
    *,
    uidvalidity: int | None = None,
    message_id: str | None = None,
    rule_name: str | None = None,
    detail: dict[str, Any] | None = None,
) -> MailEvent:
    event = MailEvent(
        account_id=account_id,
        folder=folder,
        uid=uid,
        kind=kind.value,
        uidvalidity=uidvalidity,
        message_id=message_id,
        rule_name=rule_name,
        detail=detail or {},
    )
    session.add(event)
    await session.flush()
    return event
# end def


async def list_events(session: AsyncSession, account_id: UUID, folder: str, uid: int) -> list[MailEvent]:
    """The log of one mail, oldest first."""
    query = (
        select(MailEvent)
        .where(MailEvent.account_id == account_id, MailEvent.folder == folder, MailEvent.uid == uid)
        .order_by(MailEvent.created_at, MailEvent.id)
    )
    return list((await session.scalars(query)).all())
# end def


async def list_events_by_message_id(session: AsyncSession, message_id: str, kind: EventKind | None = None) -> list[MailEvent]:
    """Everything logged for mails with this `Message-ID`, across folders and accounts, oldest first. Links a moved mail's keys."""
    query = select(MailEvent).where(MailEvent.message_id == message_id)
    if kind is not None:
        query = query.where(MailEvent.kind == kind.value)
    # end if
    return list((await session.scalars(query.order_by(MailEvent.created_at, MailEvent.id))).all())
# end def


async def has_event(
    session: AsyncSession,
    account_id: UUID,
    folder: str,
    uid: int,
    kind: EventKind,
    *,
    uidvalidity: int | None = None,
    rule_name: str | None = None,
) -> bool:
    """Whether the mail already has such an entry; `uidvalidity` tells a reused uid from the old mail."""
    query = select(MailEvent.id).where(
        MailEvent.account_id == account_id,
        MailEvent.folder == folder,
        MailEvent.uid == uid,
        MailEvent.kind == kind.value,
        MailEvent.uidvalidity.is_(None) if uidvalidity is None else MailEvent.uidvalidity == uidvalidity,
        MailEvent.rule_name.is_(None) if rule_name is None else MailEvent.rule_name == rule_name,
    )
    return (await session.scalars(query.limit(1))).first() is not None
# end def
