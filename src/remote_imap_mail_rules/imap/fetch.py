"""Parsing of `FETCH`, `LIST`, `STATUS` and `SELECT` responses."""

import re
from datetime import datetime
from email.utils import parsedate_to_datetime

from .models import FetchedMessage, FolderCounts, FolderInfo, FolderState
from .sexpr import Chunk, Node, parse

FETCH_START_RE = re.compile(rb"^\d+ FETCH \(", re.IGNORECASE)
LIST_RE = re.compile(r'^\((?P<attrs>[^)]*)\) (?P<delim>"(?:[^"\\]|\\.)*"|NIL) (?P<name>.*)$')


def as_int(node: Node) -> int | None:
    return int(node) if isinstance(node, str) and node.isdigit() else None
# end def


def parse_internaldate(node: Node) -> datetime | None:
    if not isinstance(node, str):
        return None
    # end if
    try:
        return parsedate_to_datetime(node)
    except (TypeError, ValueError):
        return None
    # end try
# end def


def apply_attribute(message: FetchedMessage, key: str, value: Node) -> None:
    upper = key.upper()
    if upper == "UID":
        message.uid = as_int(value)
    elif upper == "FLAGS":
        message.flags = frozenset(item for item in value if isinstance(item, str)) if isinstance(value, list) else frozenset()
    elif upper == "INTERNALDATE":
        message.internaldate = parse_internaldate(value)
    elif upper == "RFC822.SIZE":
        message.size = as_int(value)
    elif upper == "MODSEQ":
        message.modseq = as_int(value[0]) if isinstance(value, list) and value else None
    elif upper == "BODYSTRUCTURE":
        message.bodystructure = value
    elif upper.startswith("BODY[") and isinstance(value, bytes):
        message.sections[upper.removeprefix("BODY[").split("]")[0]] = value
    # end if
# end def


def parse_fetch(lines: list[Chunk]) -> list[FetchedMessage]:
    """Parses the lines of a FETCH response. Messages are split at their `n FETCH (` line."""
    groups: list[list[Chunk]] = []
    for line in lines:
        if isinstance(line, bytes) and FETCH_START_RE.match(line):
            groups.append([line])
            continue
        # end if
        if groups and isinstance(line, bytes | bytearray):
            groups[-1].append(line)
        # end if
    # end for
    messages: list[FetchedMessage] = []
    for group in groups:
        tree = parse(group)
        if len(tree) < 3 or not isinstance(tree[2], list):
            continue
        # end if
        message = FetchedMessage(sequence=as_int(tree[0]) or 0)
        data = tree[2]
        for key, value in zip(data[::2], data[1::2], strict=False):
            if isinstance(key, str):
                apply_attribute(message, key, value)
            # end if
        # end for
        messages.append(message)
    # end for
    return messages
# end def


def parse_list(lines: list[Chunk]) -> list[FolderInfo]:
    folders: list[FolderInfo] = []
    for line in lines:
        if not isinstance(line, bytes):
            continue
        # end if
        text = line.decode("utf-8", errors="replace")
        text = text.removeprefix("LIST ").removeprefix("list ")
        match = LIST_RE.match(text)
        if match is None:
            continue
        # end if
        tree = parse([match.group("name").encode()])
        name = tree[0] if tree and isinstance(tree[0], str) else match.group("name").strip('"')
        delimiter = None if match.group("delim") == "NIL" else match.group("delim").strip('"')
        attributes = frozenset(attr.lower() for attr in match.group("attrs").split())
        folders.append(FolderInfo(name=name, attributes=attributes, delimiter=delimiter))
    # end for
    return folders
# end def


def find_number(lines: list[Chunk], name: str) -> int | None:
    """Reads `[NAME 123]` or `NAME 123` out of SELECT/EXAMINE/STATUS lines."""
    pattern = re.compile(rf"\b{name}\s+(\d+)", re.IGNORECASE)
    for line in lines:
        if not isinstance(line, bytes):
            continue
        # end if
        match = pattern.search(line.decode("utf-8", errors="replace"))
        if match:
            return int(match.group(1))
        # end if
    # end for
    return None
# end def


def parse_folder_state(lines: list[Chunk]) -> FolderState | None:
    uidvalidity = find_number(lines, "UIDVALIDITY")
    uidnext = find_number(lines, "UIDNEXT")
    if uidvalidity is None or uidnext is None:
        return None
    # end if
    return FolderState(uidvalidity=uidvalidity, uidnext=uidnext, highestmodseq=find_number(lines, "HIGHESTMODSEQ"))
# end def


def parse_folder_counts(lines: list[Chunk]) -> FolderCounts | None:
    messages = find_number(lines, "MESSAGES")
    if messages is None:
        return None
    # end if
    return FolderCounts(messages=messages, unseen=find_number(lines, "UNSEEN") or 0, uidvalidity=find_number(lines, "UIDVALIDITY"))
# end def


APPENDUID_RE = re.compile(r"\[APPENDUID (\d+) (\d+)\]", re.IGNORECASE)
COPYUID_RE = re.compile(r"\[COPYUID (\d+) [\d:,]+ (\d+)\]", re.IGNORECASE)


def parse_new_uid(lines: list[Chunk]) -> tuple[int, int] | None:
    """`(uidvalidity, uid)` of the new copy from an `APPENDUID` / `COPYUID` response code (UIDPLUS), `None` without one or for several mails."""
    for line in lines:
        if not isinstance(line, bytes):
            continue
        # end if
        text = line.decode("utf-8", errors="replace")
        match = APPENDUID_RE.search(text) or COPYUID_RE.search(text)
        if match:
            return int(match.group(1)), int(match.group(2))
        # end if
    # end for
    return None
# end def


def parse_search(lines: list[Chunk]) -> list[int]:
    uids: list[int] = []
    for line in lines:
        if not isinstance(line, bytes):
            continue
        # end if
        text = line.decode("utf-8", errors="replace").removeprefix("SEARCH").strip()
        uids.extend(int(token) for token in text.split() if token.isdigit())
    # end for
    return uids
# end def
