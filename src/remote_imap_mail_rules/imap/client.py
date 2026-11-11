"""Async IMAP client. Reading only ever uses `EXAMINE` and `BODY.PEEK`; the write methods (`store_flags`, `move`, `delete`, `append`) open the folder with `SELECT` or `APPEND`."""

import asyncio
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
from .fetch import parse_fetch, parse_folder_counts, parse_folder_state, parse_list, parse_new_uid, parse_search
from .models import FetchedMessage, FolderCounts, FolderInfo, FolderState, Moved, RawMessage
from .sexpr import Chunk
from .transfer import decode_transfer

FETCH_FIELDS = "(UID FLAGS INTERNALDATE RFC822.SIZE BODYSTRUCTURE BODY.PEEK[HEADER])"
FETCH_FIELDS_CONDSTORE = "(UID FLAGS INTERNALDATE RFC822.SIZE BODYSTRUCTURE BODY.PEEK[HEADER] MODSEQ)"
UID_BATCH = 200

logger = logging.getLogger(__name__)


class ImapError(Exception):
    """The server answered `NO` / `BAD` or something unexpected."""
# end class


TRANSIENT_LOGIN_CODES = ("UNAVAILABLE", "SERVERBUG", "INUSE", "LIMIT")


class ImapLoginError(ImapError):
    """The server refused the `LOGIN`. `transient` is set when its response code (RFC 5530) says the credentials are not the reason."""

    def __init__(self, response: aioimaplib.Response) -> None:
        self.server_text = " ".join(line.decode("utf-8", errors="replace") if isinstance(line, bytes) else str(line) for line in response.lines)
        self.transient = any(f"[{code}" in self.server_text.upper() for code in TRANSIENT_LOGIN_CODES)
        super().__init__(f"login failed: {response.result} {response.lines!r}")
    # end def
# end class


def check_login(response: aioimaplib.Response) -> aioimaplib.Response:
    if response.result != "OK":
        raise ImapLoginError(response)
    # end if
    return response
# end def


ConnectionFactory = Callable[[ImapSettings], ImapConnection]


def connect_aioimaplib(settings: ImapSettings) -> ImapConnection:
    if settings.imap_ssl:
        return aioimaplib.IMAP4_SSL(  # type: ignore[return-value]
            host=settings.imap_host, port=settings.imap_port, timeout=settings.imap_timeout, ssl_context=ssl.create_default_context(),
        )
    # end if
    return aioimaplib.IMAP4(host=settings.imap_host, port=settings.imap_port, timeout=settings.imap_timeout)  # type: ignore[return-value]
# end def


async def cancel_leftover_tasks(connection: ImapConnection) -> None:
    """Cancels the tasks `aioimaplib` keeps in `IMAP4.tasks`.

    `idle_start` runs `IDLE` as a task that a cancelled caller does not stop, and a connection closed that way would be garbage collected with it
    pending ("Task was destroyed but it is pending!").
    """
    leftovers = [task for task in connection.tasks if not task.done()]
    for task in leftovers:
        task.cancel()
    # end for
    await asyncio.gather(*leftovers, return_exceptions=True)
# end def


async def release(connection: ImapConnection) -> None:
    """Ends `IDLE`, logs out (best effort) and cancels the tasks `aioimaplib` leaves behind, so nothing is garbage collected while pending."""
    try:
        if connection.has_pending_idle():
            connection.idle_done()
        # end if
        await connection.logout()
    except (TimeoutError, aioimaplib.AioImapException, OSError):
        pass
    finally:
        await cancel_leftover_tasks(connection)
    # end try
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
        self.writable = False
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
        try:
            await connection.wait_hello_from_server()
            check_login(await connection.login(self.settings.imap_username, self.settings.imap_password.get_secret_value()))
        except BaseException:
            # Not ours yet, so `close()` would never see it: a rejected, timed out or cancelled login must not leave its tasks pending.
            await release(connection)
            raise
        # end try
        self.connection = connection
    # end def

    async def close(self) -> None:
        connection, self.connection = self.connection, None
        if connection is not None:
            await release(connection)
        # end if
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
        # `aioimaplib` only moves to SELECTED on `select()`, not on `examine()`, and then refuses SEARCH / FETCH / IDLE with
        # "command SEARCH illegal in state AUTH". The server did open the folder, so tell the library.
        self.conn.protocol.state = aioimaplib.SELECTED
        self.folder, self.state, self.writable = folder, state, False
        return state
    # end def

    async def select(self, folder: str) -> FolderState:
        """Opens the folder read-write. Only needed for the write methods, which call it themselves."""
        response = check(await self.conn.select(quote_folder(folder)), f"select {folder}")
        state = parse_folder_state(response.lines)
        if state is None:
            raise ImapError(f"select {folder} gave no UIDVALIDITY/UIDNEXT: {response.lines!r}")
        # end if
        self.folder, self.state, self.writable = folder, state, True
        return state
    # end def

    async def ensure_writable(self, folder: str) -> None:
        if self.folder != folder or not self.writable:
            await self.select(folder)
        # end if
    # end def

    async def store_flags(self, folder: str, uid: int, add: tuple[str, ...] = (), remove: tuple[str, ...] = ()) -> None:
        """Adds and removes flags or keywords of one mail."""
        await self.ensure_writable(folder)
        for sign, flags in (("+", add), ("-", remove)):
            if flags:
                check(await self.conn.uid("store", str(uid), f"{sign}FLAGS.SILENT", f"({' '.join(flags)})"), "store")
            # end if
        # end for
    # end def

    def moved(self, target: str, lines: list[Chunk]) -> Moved:
        new = parse_new_uid(lines)
        return Moved(folder=target, uid=new[1], uidvalidity=new[0]) if new else Moved(folder=target)
    # end def

    async def move(self, folder: str, uid: int, target: str) -> Moved:
        """Moves one mail to another folder of this account and says where it went. Without `MOVE` it is copy, flag `\\Deleted` and a `UID EXPUNGE` of just that mail."""
        await self.ensure_writable(folder)
        target = await self.resolve_folder(target)
        if self.has_capability("MOVE"):
            return self.moved(target, check(await self.conn.uid("move", str(uid), quote_folder(target)), f"move to {target}").lines)
        # end if
        self.require_safe_delete("move")
        moved = self.moved(target, check(await self.conn.uid("copy", str(uid), quote_folder(target)), f"copy to {target}").lines)
        await self.delete(folder, uid)
        return moved
    # end def

    def require_safe_delete(self, what: str) -> None:
        if not self.has_capability("UIDPLUS"):
            # A plain EXPUNGE would also remove unrelated mails flagged `\Deleted`, so refuse instead.
            raise ImapError(f"cannot {what} safely: the server has neither MOVE nor UIDPLUS")
        # end if
    # end def

    async def delete(self, folder: str, uid: int) -> None:
        """Flags one mail `\\Deleted` and expunges just that UID. Refused without `UIDPLUS`."""
        self.require_safe_delete("delete")
        await self.ensure_writable(folder)
        check(await self.conn.uid("store", str(uid), "+FLAGS.SILENT", "(\\Deleted)"), "store")
        check(await self.conn.uid("expunge", str(uid)), "expunge")
    # end def

    async def append(self, folder: str, message: RawMessage) -> Moved:
        """Stores a whole mail in a folder, with its flags and internal date. The new UID is known with `UIDPLUS`."""
        folder = await self.resolve_folder(folder)
        flags = " ".join(sorted(flag for flag in message.flags if flag.lower() != "\\recent")) or None
        response = check(await self.conn.append(message.raw, quote_folder(folder), flags, message.internaldate), f"append to {folder}")
        return self.moved(folder, response.lines)
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

    async def resolve_folder(self, name: str) -> str:
        """The server's real name for a folder as written in a rule, where `/` means subfolder.

        A name the server lists is kept. Otherwise `/` becomes the server's delimiter, the namespace prefix (`INBOX.` on Dovecot) is added
        if the server keeps its folders there, and case is ignored. A folder that does not exist yet gets the converted, prefixed name.
        """
        found = await self.list_folders("*")
        listed = [info.name for info in found]
        if name in listed:
            return name
        # end if
        delimiter = next((info.delimiter for info in found if info.delimiter), "/")
        converted = name.replace("/", delimiter)
        inbox = f"INBOX{delimiter}"
        prefixed = any(entry.upper().startswith(inbox.upper()) for entry in listed)
        candidates = [converted] + ([inbox + converted] if prefixed and not converted.upper().startswith(inbox.upper()) else [])
        for candidate in candidates:
            if candidate in listed:
                return candidate
            # end if
        # end for
        for candidate in candidates:
            lowered = candidate.lower()
            match = next((entry for entry in listed if entry.lower() == lowered), None)
            if match is not None:
                return match
            # end if
        # end for
        return candidates[-1]
    # end def

    async def expand_folder(self, folder: str, recursive: bool) -> list[str]:
        """The folder itself plus, if `recursive`, all selectable folders below it. Empty if the folder does not exist."""
        folder = await self.resolve_folder(folder)
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
        """All mails of the folder, oldest first (lowest UID), one page at a time."""
        await self.examine(folder)
        uids = sorted(await self.search_uids("ALL"))
        for start in range(0, len(uids), page_size):
            page = await self.fetch_mails(account_id, folder, uids[start : start + page_size])
            if page:
                yield page[::-1]
            # end if
        # end for
    # end def

    async def list_uids(self, folder: str, before_uid: int | None = None) -> list[int]:
        """The UIDs of a folder, newest first, only those below `before_uid` if given."""
        await self.examine(folder)
        uids = sorted(await self.search_uids("ALL"), reverse=True)
        return [uid for uid in uids if before_uid is None or uid < before_uid]
    # end def

    async def folder_counts(self, folder: str) -> FolderCounts:
        """Total and unseen mails of a folder without selecting it."""
        response = check(await self.conn.status(quote_folder(folder), "(MESSAGES UNSEEN)"), f"status {folder}")
        counts = parse_folder_counts(response.lines)
        if counts is None:
            raise ImapError(f"status {folder} gave no counts: {response.lines!r}")
        # end if
        return counts
    # end def

    async def list_page(self, account_id: UUID, folder: str, limit: int, before_uid: int | None = None) -> tuple[list[Mail], int]:
        """One page of a folder, newest first, starting below `before_uid`, and the total number of mails in the folder."""
        await self.examine(folder)
        uids = sorted(await self.search_uids("ALL"), reverse=True)
        older = [uid for uid in uids if before_uid is None or uid < before_uid]
        return await self.fetch_mails(account_id, folder, older[:limit]), len(uids)
    # end def

    async def fetch_message(self, account_id: UUID, folder: str, uid: int) -> Mail | None:
        """Headers and structure of one mail, or `None` if the UID does not exist."""
        await self.examine(folder)
        mails = await self.fetch_mails(account_id, folder, [uid])
        return mails[0] if mails else None
    # end def

    async def fetch_raw(self, folder: str, uid: int) -> RawMessage | None:
        """The whole mail with flags and internal date (`BODY.PEEK[]`, so nothing is marked seen), or `None` if the UID does not exist."""
        await self.examine(folder)
        fetched = next(iter(await self.fetch(str(uid), "(UID FLAGS INTERNALDATE BODY.PEEK[])")), None)
        if fetched is None or fetched.uid is None or "" not in fetched.sections:
            return None
        # end if
        return RawMessage(uid=fetched.uid, raw=fetched.sections[""], flags=fetched.flags, internaldate=fetched.internaldate)
    # end def

    async def find_message_id(self, folder: str, message_id: str) -> int | None:
        """The UID of the mail with this `Message-ID` header in a folder, if any. Used to not copy a mail twice."""
        await self.examine(folder)
        escaped = message_id.replace("\\", "\\\\").replace('"', '\\"')
        uids = await self.search_uids("HEADER", "Message-ID", f'"{escaped}"')
        return uids[0] if uids else None
    # end def

    async def fetch_part(self, folder: str, uid: int, number: str) -> tuple[Part, bytes] | None:
        """One part of a mail with its transfer encoding undone, or `None` if the mail or part does not exist."""
        if self.folder != folder:
            await self.examine(folder)
        # end if
        structure = next(iter(await self.fetch(str(uid), "(UID BODYSTRUCTURE)")), None)
        part = next((item for item in parse_parts(structure.bodystructure) if item.number == number), None) if structure else None
        if part is None or part.mime_type.startswith("multipart/"):
            return None
        # end if
        fetched = await self.fetch(str(uid), f"(UID BODY.PEEK[{number}])")
        data = next((item.sections[number] for item in fetched if number in item.sections), None)
        if data is None:
            return None
        # end if
        return part, decode_transfer(part.encoding, data)
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
            Attachment(
                mime_type=part.mime_type,
                filename=part.filename,
                size=part.size,
                inline=part.inline,
                part=part.number,
                content_id=part.content_id,
            )
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
            uidvalidity=self.state.uidvalidity if self.state is not None and self.folder == folder else None,
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
