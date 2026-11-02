"""Read-only async IMAP client: folders are only ever opened with `EXAMINE`, nothing here writes to the mailbox."""

import logging
import ssl
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager
from email import message_from_bytes, policy
from email.message import Message
from types import TracebackType
from uuid import UUID

import aioimaplib

from ..config import ImapSettings
from ..mail import Attachment, Bodies, Mail
from .bodystructure import Part, parse_parts
from .connection import ImapConnection
from .fetch import parse_fetch, parse_folder_state, parse_list, parse_search
from .models import FetchedMessage, FolderInfo, FolderState

FETCH_FIELDS = "(UID FLAGS INTERNALDATE RFC822.SIZE BODYSTRUCTURE BODY.PEEK[HEADER])"
FETCH_FIELDS_CONDSTORE = "(UID FLAGS INTERNALDATE RFC822.SIZE BODYSTRUCTURE BODY.PEEK[HEADER] MODSEQ)"
UID_BATCH = 200

logger = logging.getLogger(__name__)


class ImapError(Exception):
    """The server answered `NO` / `BAD` or something unexpected."""
# end class


ConnectionFactory = Callable[[ImapSettings], ImapConnection]


def connect_aioimaplib(settings: ImapSettings) -> ImapConnection:
    if settings.imap_ssl:
        return aioimaplib.IMAP4_SSL(host=settings.imap_host, port=settings.imap_port, ssl_context=ssl.create_default_context())  # type: ignore[return-value]
    # end if
    return aioimaplib.IMAP4(host=settings.imap_host, port=settings.imap_port)  # type: ignore[return-value]
# end def


def check(response: aioimaplib.Response, what: str) -> aioimaplib.Response:
    if response.result != "OK":
        raise ImapError(f"{what} failed: {response.result} {response.lines!r}")
    # end if
    return response
# end def


def uid_ranges(uids: list[int]) -> list[str]:
    """Comma separated UID sets of at most `UID_BATCH` entries each."""
    return [",".join(str(uid) for uid in uids[start : start + UID_BATCH]) for start in range(0, len(uids), UID_BATCH)]
# end def


def decode_part(part: Part, data: bytes) -> str | None:
    """Decodes the transfer encoding and charset of a text part by letting the `email` package parse it."""
    charset = part.params.get("charset", "utf-8")
    raw = f"Content-Type: {part.mime_type}; charset=\"{charset}\"\r\nContent-Transfer-Encoding: {part.encoding}\r\n\r\n".encode() + data
    try:
        message = message_from_bytes(raw, policy=policy.default)
        content = message.get_content()
    except (LookupError, ValueError):
        return data.decode("utf-8", errors="replace")
    # end try
    return content if isinstance(content, str) else None
# end def


class ImapClient(AbstractAsyncContextManager["ImapClient"]):
    """One connection to one account, with one folder examined at a time."""

    def __init__(self, settings: ImapSettings, factory: ConnectionFactory = connect_aioimaplib) -> None:
        self.settings = settings
        self.factory = factory
        self.connection: ImapConnection | None = None
        self.folder: str | None = None
        self.state: FolderState | None = None
    # end def

    async def __aenter__(self) -> "ImapClient":
        await self.connect()
        return self
    # end def

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, traceback: TracebackType | None) -> None:
        await self.close()
    # end def

    async def connect(self) -> None:
        connection = self.factory(self.settings)
        await connection.wait_hello_from_server()
        check(await connection.login(self.settings.imap_username, self.settings.imap_password.get_secret_value()), "login")
        self.connection = connection
    # end def

    async def close(self) -> None:
        connection, self.connection = self.connection, None
        if connection is None:
            return
        # end if
        try:
            if connection.has_pending_idle():
                connection.idle_done()
            # end if
            await connection.logout()
        except (TimeoutError, aioimaplib.AioImapException, OSError):
            pass
        # end try
    # end def

    @property
    def conn(self) -> ImapConnection:
        if self.connection is None:
            raise ImapError("not connected")
        # end if
        return self.connection
    # end def

    def has_capability(self, name: str) -> bool:
        return name.upper() in {item.upper() for item in self.conn.protocol.capabilities}
    # end def

    @property
    def condstore(self) -> bool:
        return self.has_capability("CONDSTORE")
    # end def

    async def examine(self, folder: str) -> FolderState:
        """Opens the folder read-only."""
        response = check(await self.conn.examine(quote_folder(folder)), f"examine {folder}")
        state = parse_folder_state(response.lines)
        if state is None:
            raise ImapError(f"examine {folder} gave no UIDVALIDITY/UIDNEXT: {response.lines!r}")
        # end if
        self.folder, self.state = folder, state
        return state
    # end def

    async def poll_state(self, folder: str) -> FolderState:
        """The current state of a folder without selecting it."""
        names = "(UIDNEXT UIDVALIDITY HIGHESTMODSEQ)" if self.condstore else "(UIDNEXT UIDVALIDITY)"
        response = check(await self.conn.status(quote_folder(folder), names), f"status {folder}")
        state = parse_folder_state(response.lines)
        if state is None:
            raise ImapError(f"status {folder} gave no state: {response.lines!r}")
        # end if
        return state
    # end def

    async def list_folders(self, pattern: str = "*") -> list[FolderInfo]:
        return parse_list(check(await self.conn.list('""', quote_folder(pattern)), "list").lines)
    # end def

    async def expand_folder(self, folder: str, recursive: bool) -> list[str]:
        """The folder itself plus, if `recursive`, all selectable folders below it. Empty if the folder does not exist."""
        found = await self.list_folders(f"{folder}*")
        names = [info.name for info in found if info.name == folder and info.selectable]
        if not names:
            logger.warning("Folder %r does not exist (or cannot be selected), skipping it.", folder)
            return []
        # end if
        if not recursive:
            return names
        # end if
        for info in found:
            delimiter = info.delimiter or "/"
            if info.selectable and info.name.startswith(folder + delimiter):
                names.append(info.name)
            # end if
        # end for
        return names
    # end def

    async def search_uids(self, *criteria: str) -> list[int]:
        return sorted(parse_search(check(await self.conn.uid_search(*criteria), "search").lines))
    # end def

    async def fetch(self, uid_set: str, fields: str) -> list[FetchedMessage]:
        response = check(await self.conn.uid("fetch", uid_set, fields), "fetch")
        return parse_fetch(response.lines)
    # end def

    async def fetch_mails(self, account_id: UUID, folder: str, uids: list[int]) -> list[Mail]:
        """Headers, flags and structure of the given mails, newest UID first. Bodies load lazily later."""
        fields = FETCH_FIELDS_CONDSTORE if self.condstore else FETCH_FIELDS
        mails: list[Mail] = []
        for uid_set in uid_ranges(uids):
            for fetched in await self.fetch(uid_set, fields):
                mail = self.build_mail(account_id, folder, fetched)
                if mail is not None:
                    mails.append(mail)
                # end if
            # end for
        # end for
        return sorted(mails, key=lambda mail: mail.uid, reverse=True)
    # end def

    async def iter_pages(self, account_id: UUID, folder: str, page_size: int) -> AsyncIterator[list[Mail]]:
        """All mails of the folder, newest first, one page at a time."""
        await self.examine(folder)
        uids = sorted(await self.search_uids("ALL"), reverse=True)
        for start in range(0, len(uids), page_size):
            page = await self.fetch_mails(account_id, folder, uids[start : start + page_size])
            if page:
                yield page
            # end if
        # end for
    # end def

    async def fetch_new(self, account_id: UUID, folder: str, since_uid: int) -> list[Mail]:
        """Mails with a UID above `since_uid`."""
        found = [uid for uid in await self.search_uids(f"UID {since_uid + 1}:*") if uid > since_uid]
        return await self.fetch_mails(account_id, folder, found)
    # end def

    async def fetch_changed(self, account_id: UUID, folder: str, since_modseq: int) -> list[Mail]:
        """Mails whose flags changed since `since_modseq` (needs CONDSTORE)."""
        if not self.condstore:
            return []
        # end if
        fields = f"{FETCH_FIELDS_CONDSTORE} (CHANGEDSINCE {since_modseq})"
        mails = [mail for fetched in await self.fetch("1:*", fields) if (mail := self.build_mail(account_id, folder, fetched)) is not None]
        return sorted(mails, key=lambda mail: mail.uid, reverse=True)
    # end def

    def build_mail(self, account_id: UUID, folder: str, fetched: FetchedMessage) -> Mail | None:
        if fetched.uid is None:
            return None
        # end if
        header = fetched.sections.get("HEADER", b"")
        headers: Message = message_from_bytes(header, policy=policy.default)
        parts = parse_parts(fetched.bodystructure)
        top = parts[0].mime_type if parts else None
        uid = fetched.uid
        attachments = [
            Attachment(mime_type=part.mime_type, filename=part.filename, size=part.size, inline=part.inline)
            for part in parts
            if part.is_attachment
        ]

        async def load_bodies() -> Bodies:
            return await self.load_bodies(folder, uid, parts)
        # end def

        return Mail(
            account_id=account_id,
            folder=folder,
            uid=uid,
            headers=headers,
            flags=fetched.flags,
            date_received=fetched.internaldate,
            size=fetched.size,
            modseq=fetched.modseq,
            mime_type=top,
            attachments=attachments,
            body_loader=load_bodies,
        )
    # end def

    async def load_bodies(self, folder: str, uid: int, parts: list[Part]) -> Bodies:
        """Downloads and decodes the non-attachment text parts. The folder must be the examined one."""
        if self.folder != folder:
            await self.examine(folder)
        # end if
        texts: dict[str, list[str]] = {"text/plain": [], "text/html": []}
        for part in parts:
            if part.mime_type not in texts or part.is_attachment:
                continue
            # end if
            fetched = await self.fetch(str(uid), f"(BODY.PEEK[{part.number}])")
            data = next((item.sections[part.number] for item in fetched if part.number in item.sections), None)
            if data is None:
                continue
            # end if
            decoded = decode_part(part, data)
            if decoded is not None:
                texts[part.mime_type].append(decoded)
            # end if
        # end for
        return Bodies(
            text="\n".join(texts["text/plain"]) if texts["text/plain"] else None,
            html="\n".join(texts["text/html"]) if texts["text/html"] else None,
        )
    # end def
# end class


def quote_folder(folder: str) -> str:
    escaped = folder.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
# end def
