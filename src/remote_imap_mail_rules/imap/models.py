"""Plain data of the IMAP layer."""

from dataclasses import dataclass, field
from datetime import datetime

from .sexpr import Node


@dataclass(frozen=True)
class FolderState:
    """What a server told us about a selected or polled folder."""

    uidvalidity: int
    uidnext: int
    highestmodseq: int | None = None
# end class


@dataclass
class FetchedMessage:
    """One parsed `FETCH` response."""

    sequence: int
    uid: int | None = None
    flags: frozenset[str] = frozenset()
    internaldate: datetime | None = None
    size: int | None = None
    modseq: int | None = None
    bodystructure: Node = None
    sections: dict[str, bytes] = field(default_factory=dict)
# end class


@dataclass(frozen=True)
class Moved:
    """Where a mail ended up after `move` / `append`. `uid` and `uidvalidity` are `None` when the server sent no `COPYUID` / `APPENDUID` (no `UIDPLUS`)."""

    folder: str
    uid: int | None = None
    uidvalidity: int | None = None
# end class


@dataclass(frozen=True)
class RawMessage:
    """A whole mail as the server stores it, for copying it to another account."""

    uid: int
    raw: bytes
    flags: frozenset[str]
    internaldate: datetime | None
# end class


@dataclass(frozen=True)
class FolderCounts:
    """`STATUS (MESSAGES UNSEEN)` of a folder."""

    messages: int
    unseen: int
# end class


SPECIAL_USE = ("inbox", "sent", "drafts", "trash", "junk", "archive", "flagged", "all")
SPECIAL_USE_ATTRIBUTES = {
    "\\sent": "sent",
    "\\drafts": "drafts",
    "\\trash": "trash",
    "\\junk": "junk",
    "\\archive": "archive",
    "\\flagged": "flagged",
    "\\all": "all",
}


@dataclass(frozen=True)
class FolderInfo:
    name: str
    attributes: frozenset[str]
    delimiter: str | None

    @property
    def selectable(self) -> bool:
        return "\\noselect" not in self.attributes and "\\nonexistent" not in self.attributes
    # end def

    @property
    def special_use(self) -> str | None:
        """One of `SPECIAL_USE`, from the RFC 6154 attributes, and `inbox` for `INBOX`."""
        if self.name.upper() == "INBOX":
            return "inbox"
        # end if
        for attribute, use in SPECIAL_USE_ATTRIBUTES.items():
            if attribute in self.attributes:
                return use
            # end if
        # end for
        return None
    # end def
# end class


class ChangeKind:
    """Why a watcher woke up."""

    push = "push"
    poll = "poll"
# end class


@dataclass(frozen=True)
class ChangeEvent:
    kind: str
    folder: str
# end class
