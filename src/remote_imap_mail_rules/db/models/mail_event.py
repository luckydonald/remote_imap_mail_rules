"""One entry of the action log of a mail."""

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base
from .account import utcnow


class EventKind(StrEnum):
    """`action` is written when rules run their actions, `user_action` when the watcher sees a change on the server that no rule made."""

    first_seen = "first_seen"
    rule_match = "rule_match"
    action = "action"
    user_action = "user_action"
# end class


class MailEvent(Base):
    """A mail is identified by account, folder, `uidvalidity` and `uid`; `message_id` survives moves between accounts."""

    __tablename__ = "mail_events"
    __table_args__ = (Index("ix_mail_events_mail", "account_id", "folder", "uid"),)

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    account_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("accounts.id", ondelete="CASCADE"))
    folder: Mapped[str] = mapped_column(String(1024))
    uidvalidity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    uid: Mapped[int] = mapped_column(Integer)
    message_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str] = mapped_column(String(32))
    rule_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    detail: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
# end class
