"""The git settings of the rules folder: one row, edited in the web UI."""

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base

ROW_ID = 1


class GitSettings(Base):
    __tablename__ = "git_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=ROW_ID)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_commit: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_push: Mapped[bool] = mapped_column(Boolean, default=False)
    remote_url: Mapped[str] = mapped_column(String(1024), default="")
    branch: Mapped[str] = mapped_column(String(255), default="main")
    auth_method: Mapped[str] = mapped_column(String(16), default="none")
    username: Mapped[str] = mapped_column(String(255), default="")
    token_encrypted: Mapped[str] = mapped_column(Text, default="")
    author_name: Mapped[str] = mapped_column(String(255), default="remote_imap_mail_rules")
    author_email: Mapped[str] = mapped_column(String(255), default="rules@localhost")
# end class
