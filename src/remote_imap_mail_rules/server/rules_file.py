"""Reading, validating and atomically writing the rules file."""

import asyncio
import os
import tempfile
from pathlib import Path

import yaml
from pydantic import ValidationError

from ..rules.loader import parse_rules


class InvalidRules(Exception):
    """The text is not a valid rules file; `messages` are readable lines for the editor."""

    def __init__(self, messages: list[str]) -> None:
        super().__init__("; ".join(messages))
        self.messages = messages
    # end def
# end class


def validate(text: str) -> None:
    try:
        parse_rules(text)
    except yaml.YAMLError as e:
        raise InvalidRules([f"YAML: {e}"]) from e
    except ValidationError as e:
        raise InvalidRules([f"{'.'.join(str(part) for part in err['loc']) or '(root)'}: {err['msg']}" for err in e.errors()]) from e
    # end try
# end def


def write_atomic(path: Path, text: str) -> None:
    """Writes to a temp file in the same folder, then replaces, so a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="") as file:
            file.write(text)
        # end with
        if path.exists():
            os.chmod(temp_name, path.stat().st_mode & 0o777)
        # end if
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise
    # end try
# end def


async def read_text(path: Path) -> str | None:
    """The file content, or `None` when it does not exist yet."""
    try:
        return await asyncio.to_thread(path.read_text, encoding="utf-8")
    except FileNotFoundError:
        return None
    # end try
# end def


async def save_text(path: Path, text: str) -> None:
    """Validates first; raises `InvalidRules` and writes nothing when invalid."""
    await asyncio.to_thread(validate, text)
    await asyncio.to_thread(write_atomic, path, text)
# end def
