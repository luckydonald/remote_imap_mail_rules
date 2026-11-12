"""Repository of the action log per mail."""

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Select, String, cast, delete, func, or_, select
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


def as_utc(value: datetime) -> datetime:
    """The stored times are UTC; SQLite hands them back without a zone, so a naive value counts as UTC."""
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
# end def


def like_pattern(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"
# end def


def filter_log(
    query: Select[Any],
    *,
    account_id: UUID | None = None,
    folder: str | None = None,
    kinds: Sequence[EventKind] = (),
    rule: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    text: str | None = None,
) -> Select[Any]:
    """The `WHERE` of the log filters, shared by listing and clearing."""
    if account_id is not None:
        query = query.where(MailEvent.account_id == account_id)
    # end if
    if folder is not None:
        query = query.where(MailEvent.folder == folder)
    # end if
    if kinds:
        query = query.where(MailEvent.kind.in_([kind.value for kind in kinds]))
    # end if
    if rule is not None:
        query = query.where(MailEvent.rule_name == rule)
    # end if
    if since is not None:
        query = query.where(MailEvent.created_at >= as_utc(since))
    # end if
    if until is not None:
        query = query.where(MailEvent.created_at <= as_utc(until))
    # end if
    if text:
        pattern = like_pattern(text)
        query = query.where(or_(*(column.ilike(pattern, escape="\\") for column in (
            MailEvent.rule_name, MailEvent.folder, MailEvent.message_id, cast(MailEvent.detail, String),
        ))))
    # end if
    return query
# end def


async def list_log(
    session: AsyncSession,
    *,
    account_id: UUID | None = None,
    folder: str | None = None,
    kinds: Sequence[EventKind] = (),
    rule: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    text: str | None = None,
    before: tuple[datetime, UUID] | None = None,
    limit: int = 50,
) -> list[MailEvent]:
    """The log across all mails, newest first. `before` is the `(created_at, id)` of the last entry of the previous page.

    `text` looks (case insensitive) into the rule name, folder, `Message-ID` and the detail.
    """
    query = filter_log(select(MailEvent), account_id=account_id, folder=folder, kinds=kinds, rule=rule, since=since, until=until, text=text)
    if before is not None:
        created, event_id = before
        query = query.where(or_(MailEvent.created_at < as_utc(created), (MailEvent.created_at == as_utc(created)) & (MailEvent.id < event_id)))
    # end if
    return list((await session.scalars(query.order_by(MailEvent.created_at.desc(), MailEvent.id.desc()).limit(limit))).all())
# end def


async def delete_log(
    session: AsyncSession,
    *,
    account_id: UUID | None = None,
    folder: str | None = None,
    kinds: Sequence[EventKind] = (),
    rule: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    text: str | None = None,
) -> int:
    """Deletes the entries the filters select (all of them without filters) and returns how many."""
    ids = filter_log(select(MailEvent.id), account_id=account_id, folder=folder, kinds=kinds, rule=rule, since=since, until=until, text=text)
    result = await session.execute(delete(MailEvent).where(MailEvent.id.in_(ids)))
    return int(result.rowcount or 0)  # type: ignore[attr-defined]
# end def


async def last_event_at(session: AsyncSession, kinds: Sequence[EventKind]) -> datetime | None:
    """When the newest entry of one of these kinds was logged."""
    newest = await session.scalar(select(func.max(MailEvent.created_at)).where(MailEvent.kind.in_([kind.value for kind in kinds])))
    return None if newest is None else as_utc(newest)
# end def
