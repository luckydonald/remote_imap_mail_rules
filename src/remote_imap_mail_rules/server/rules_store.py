"""Where the rules live: a file, or the database."""

import asyncio
from pathlib import Path
from typing import Literal, Protocol
from uuid import UUID

import yaml
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..db import rules as rule_rows
from ..rules.comments import append_comments
from ..rules.loader import parse_rule_file, parse_rules
from . import rules_file


MIRROR_NAME = "rules.yml"


class RulesStore(Protocol):
    source: Literal["file", "database"]
    file_name: str | None

    async def exists(self) -> bool: ...

    async def read_text(self) -> str | None:
        """The YAML text, or `None` when nothing is stored yet."""
        ...

    async def save_text(self, text: str) -> None:
        """Validates first; raises `rules_file.InvalidRules` and stores nothing when invalid."""
        ...
# end class


class FileRulesStore:
    source: Literal["file", "database"] = "file"

    def __init__(self, path: Path) -> None:
        self.path = path
        self.file_name: str | None = path.name
    # end def

    async def exists(self) -> bool:
        return self.path.is_file()
    # end def

    async def read_text(self) -> str | None:
        return await rules_file.read_text(self.path)
    # end def

    async def save_text(self, text: str) -> None:
        await rules_file.save_text(self.path, text)
    # end def
# end class


class DatabaseRulesStore:
    source: Literal["file", "database"] = "database"
    file_name: str | None = None

    def __init__(self, session_factory: async_sessionmaker[AsyncSession], mirror_dir: Path | None = None) -> None:
        self.session_factory = session_factory
        self.mirror_dir = mirror_dir
    # end def

    async def write_mirror(self) -> None:
        """Writes the stored rules as `rules.yml` into the mirror folder, which git tracks; nothing stored or no folder means nothing to write."""
        text = await self.read_text()
        if self.mirror_dir is not None and text is not None:
            await asyncio.to_thread(rules_file.write_atomic, self.mirror_dir / MIRROR_NAME, text)
        # end if
    # end def

    async def exists(self) -> bool:
        return await self.read_text() is not None
    # end def

    async def read_text(self) -> str | None:
        async with self.session_factory() as session:
            rule_file = await rule_rows.load_rule_file(session)
        # end with
        return None if rule_file is None else rule_rows.to_yaml(rule_file)
    # end def

    async def save_text(self, text: str) -> None:
        # The same validation as the file, then the non-concrete form is stored, so templates survive.
        await asyncio.to_thread(rules_file.validate, text)
        try:
            # The rows cannot hold YAML comments, so those of each rule are kept in its description.
            rule_file = append_comments(text, parse_rule_file(text))
        except (yaml.YAMLError, ValidationError) as e:
            raise rules_file.InvalidRules([str(e)]) from e
        # end try
        async with self.session_factory() as session:
            await rule_rows.replace_rule_file(session, rule_file)
            await session.commit()
        # end with
        await self.write_mirror()
    # end def
# end class


async def rules_referencing(store: RulesStore, account_id: UUID) -> list[str]:
    """Names of the rules with a location in this account; an unreadable or invalid rules text counts as none."""
    text = await store.read_text()
    if text is None:
        return []
    # end if
    try:
        rule_file = parse_rules(text)
    except (yaml.YAMLError, ValidationError):
        return []
    # end try
    return [rule.name for rule in rule_file.rules if any(location.account_id == account_id for location in rule.locations)]
# end def
