"""A reusable expression, the root `templates` of the rule file."""

from typing import Any

from sqlalchemy import JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class Template(Base):
    __tablename__ = "templates"

    name: Mapped[str] = mapped_column(String(255), primary_key=True)
    definition: Mapped[dict[str, Any]] = mapped_column(JSON)
# end class
