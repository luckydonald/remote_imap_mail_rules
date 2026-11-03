"""The mail as the rule evaluator sees it: IMAP metadata, parsed headers and lazily loaded bodies."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from email.message import Message
from uuid import UUID


@dataclass(frozen=True)
class Attachment:
    mime_type: str
    filename: str | None = None
    size: int | None = None
    inline: bool = False
    part: str | None = None
    content_id: str | None = None

    @property
    def extension(self) -> str | None:
        if not self.filename or "." not in self.filename:
            return None
        # end if
        return self.filename.rsplit(".", 1)[1].lower()
    # end def
# end class


@dataclass(frozen=True)
class Bodies:
    """The decoded text parts. A part that does not exist is `None`, which makes rules on it false."""

    text: str | None = None
    html: str | None = None
# end class


BodyLoader = Callable[[], Awaitable[Bodies]]


@dataclass
class Mail:
    account_id: UUID
    folder: str
    uid: int
    headers: Message
    flags: frozenset[str] = frozenset()
    date_received: datetime | None = None
    size: int | None = None
    modseq: int | None = None
    mime_type: str | None = None
    attachments: list[Attachment] = field(default_factory=list)
    body_loader: BodyLoader | None = None
    bodies: Bodies | None = None

    async def load_bodies(self) -> Bodies:
        """Fetches the body parts on first use only, so rules on cheap fields never download them."""
        if self.bodies is not None:
            return self.bodies
        # end if
        if self.body_loader is None:
            self.bodies = Bodies()
            return self.bodies
        # end if
        self.bodies = await self.body_loader()
        return self.bodies
    # end def

    def has_flag(self, flag: str) -> bool:
        return any(existing.lower() == flag.lower() for existing in self.flags)
    # end def
# end class
