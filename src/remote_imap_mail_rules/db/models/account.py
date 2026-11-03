"""An IMAP account."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


def utcnow() -> datetime:
    return datetime.now(UTC)
# end def


class Account(Base):
    """`id` is immutable and what rules refer to; `name` is a display label only."""

    __tablename__ = "accounts"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    host: Mapped[str] = mapped_column(String(255))
    port: Mapped[int] = mapped_column(Integer, default=993)
    ssl: Mapped[bool] = mapped_column(Boolean, default=True)
    username: Mapped[str] = mapped_column(String(255))
    password_encrypted: Mapped[str] = mapped_column(Text)
    page_size: Mapped[int] = mapped_column(Integer, default=50)
    poll_interval: Mapped[float] = mapped_column(Float, default=60.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
# end class
