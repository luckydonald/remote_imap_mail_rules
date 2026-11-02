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
class FolderInfo:
    name: str
    attributes: frozenset[str]
    delimiter: str | None

    @property
    def selectable(self) -> bool:
        return "\\noselect" not in self.attributes and "\\nonexistent" not in self.attributes
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
