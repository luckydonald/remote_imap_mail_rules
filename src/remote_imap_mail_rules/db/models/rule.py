"""A rule, stored as one row."""

from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from ..base import Base


class Rule(Base):
    """The JSON columns hold the non-concrete pydantic dump, so template uses and variables survive."""

    __tablename__ = "rules"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    position: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(255))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    locations: Mapped[list[Any]] = mapped_column(JSON)
    when: Mapped[dict[str, Any]] = mapped_column(JSON)
    actions: Mapped[list[Any]] = mapped_column(JSON)
# end class
