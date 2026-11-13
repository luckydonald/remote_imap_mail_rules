"""Settings of the admin that follow them into every browser: one row, edited in the web UI."""

from sqlalchemy import Boolean, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base

ROW_ID = 1


class UserSettings(Base):
    __tablename__ = "user_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=ROW_ID)
    #: The offline cache rules of the mail browser: unread mails of opened folders, mails opened while unread, the newest N of the INBOX.
    cache_unread: Mapped[bool] = mapped_column(Boolean, default=True)
    cache_opened_unread: Mapped[bool] = mapped_column(Boolean, default=True)
    cache_inbox: Mapped[bool] = mapped_column(Boolean, default=True)
    cache_inbox_count: Mapped[int] = mapped_column(Integer, default=200)
    #: Days without a view after which a cached mail is dropped (outside the INBOX window), 0 never.
    cache_max_age_days: Mapped[int] = mapped_column(Integer, default=30)
    #: When the mail view marks a mail read by itself: `off`, `open` (when it is opened) or `scrolled` (once scrolled to the end).
    auto_read: Mapped[str] = mapped_column(String(16), default="off", server_default="off")
# end class
