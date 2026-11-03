"""An in-memory IMAP server speaking just enough of `aioimaplib.IMAP4` for the client, watcher and matching tests."""

import asyncio
import re
from dataclasses import dataclass, field

import aioimaplib
from aioimaplib import Response

from remote_imap_mail_rules.config import ImapSettings


@dataclass
class FakeMessage:
    uid: int
    raw: bytes
    flags: str = ""
    modseq: int = 1
    body: bytes = b"hello"
    internaldate: str = "26-Oct-2026 08:01:00 +0000"
    structure: str | None = None
    parts: dict[str, bytes] = field(default_factory=dict)
# end class


@dataclass
class FakeFolder:
    messages: list[FakeMessage] = field(default_factory=list)
    uidvalidity: int = 1
    modseq: int = 1
# end class


@dataclass
class FakeProtocol:
    """Like `aioimaplib`: the state is AUTH after login and stays there on EXAMINE (only SELECT would change it)."""

    capabilities: set[str]
    state: str = "AUTH"
# end class


class FakeServer:
    def __init__(self, capabilities: set[str] | None = None) -> None:
        self.capabilities = capabilities if capabilities is not None else {"IMAP4REV1", "IDLE", "CONDSTORE"}
        self.folders: dict[str, FakeFolder] = {}
        self.attributes: dict[str, str] = {}
        self.commands: list[str] = []
        self.push_queues: list[asyncio.Queue[Response]] = []
    # end def

    def add(self, folder: str, uid: int, subject: str, flags: str = "", sender: str = "a@example.com") -> FakeMessage:
        target = self.folders.setdefault(folder, FakeFolder())
        raw = f"From: {sender}\r\nSubject: {subject}\r\n\r\n".encode()
        target.modseq += 1
        message = FakeMessage(uid=uid, raw=raw, flags=flags, modseq=target.modseq)
        target.messages.append(message)
        return message
    # end def

    def set_flags(self, folder: str, uid: int, flags: str) -> None:
        target = self.folders[folder]
        target.modseq += 1
        for message in target.messages:
            if message.uid == uid:
                message.flags, message.modseq = flags, target.modseq
            # end if
        # end for
    # end def

    def push(self) -> None:
        """Simulates the server announcing a change to everybody in IDLE."""
        for queue in self.push_queues:
            queue.put_nowait(Response("OK", [b"1 EXISTS"]))
        # end for
    # end def

    def connect(self, settings: ImapSettings) -> "FakeConnection":
        return FakeConnection(self)
    # end def
# end class


def fetch_lines(message: FakeMessage, fields: str) -> list[bytes | bytearray]:
    head = f'{message.uid} FETCH (UID {message.uid} FLAGS ({message.flags}) INTERNALDATE "{message.internaldate}" RFC822.SIZE {len(message.raw)}'
    if "MODSEQ" in fields:
        head += f" MODSEQ ({message.modseq})"
    # end if
    lines: list[bytes | bytearray] = []
    if "BODYSTRUCTURE" in fields:
        head += f" BODYSTRUCTURE {message.structure}" if message.structure else f' BODYSTRUCTURE ("text" "plain" ("charset" "utf-8") NIL NIL "7bit" {len(message.body)} 1 NIL NIL NIL)'
    # end if
    if "BODY.PEEK[HEADER]" in fields:
        lines += [f"{head} BODY[HEADER] {{{len(message.raw)}}}".encode(), bytearray(message.raw), b")"]
    elif match := re.search(r"BODY\.PEEK\[([\d.]+)\]", fields):
        data = message.parts.get(match.group(1), message.body)
        lines += [f"{head} BODY[{match.group(1)}] {{{len(data)}}}".encode(), bytearray(data), b")"]
    else:
        lines += [f"{head})".encode()]
    # end if
    return lines
# end def


class FakeConnection:
    def __init__(self, server: FakeServer) -> None:
        self.server = server
        self.protocol = FakeProtocol(server.capabilities)
        self.selected: str | None = None
        self.writable = False
        self.idle = False
        self.queue: asyncio.Queue[Response] = asyncio.Queue()
        server.push_queues.append(self.queue)
    # end def

    def log(self, command: str) -> None:
        self.server.commands.append(command)
    # end def

    def require_selected(self, command: str) -> None:
        if self.protocol.state != "SELECTED":
            raise aioimaplib.Abort(f"command {command} illegal in state {self.protocol.state}")
        # end if
    # end def

    async def wait_hello_from_server(self) -> None:
        return None
    # end def

    async def login(self, user: str, password: str) -> Response:
        self.log("LOGIN")
        return Response("OK", [b"logged in"])
    # end def

    async def logout(self) -> Response:
        self.log("LOGOUT")
        if self.queue in self.server.push_queues:
            self.server.push_queues.remove(self.queue)
        # end if
        return Response("OK", [b"bye"])
    # end def

    def folder(self, name: str) -> FakeFolder:
        return self.server.folders[name.strip('"')]
    # end def

    def state_lines(self, folder: FakeFolder) -> list[bytes]:
        lines = [f"OK [UIDVALIDITY {folder.uidvalidity}]".encode(), f"OK [UIDNEXT {max([m.uid for m in folder.messages], default=0) + 1}]".encode()]
        if "CONDSTORE" in self.server.capabilities:
            lines.append(f"OK [HIGHESTMODSEQ {folder.modseq}]".encode())
        # end if
        return lines
    # end def

    async def examine(self, mailbox: str = "INBOX") -> Response:
        self.log(f"EXAMINE {mailbox}")
        folder = self.folder(mailbox)
        self.selected = mailbox.strip('"')
        self.writable = False
        self.protocol.state = "AUTH"
        return Response("OK", self.state_lines(folder))
    # end def

    async def select(self, mailbox: str = "INBOX") -> Response:
        self.log(f"SELECT {mailbox}")
        folder = self.folder(mailbox)
        self.selected = mailbox.strip('"')
        self.writable = True
        self.protocol.state = "SELECTED"
        return Response("OK", self.state_lines(folder))
    # end def

    async def status(self, mailbox: str, names: str) -> Response:
        self.log(f"STATUS {mailbox}")
        folder = self.folder(mailbox)
        unseen = sum(1 for message in folder.messages if "\\Seen" not in message.flags)
        counts = f"{mailbox} (MESSAGES {len(folder.messages)} UNSEEN {unseen})".encode()
        return Response("OK", [*self.state_lines(folder), counts])
    # end def

    async def list(self, reference_name: str, mailbox_pattern: str) -> Response:
        self.log(f"LIST {mailbox_pattern}")
        prefix = mailbox_pattern.strip('"').rstrip("*")
        return Response("OK", [f'({self.server.attributes.get(name, "")}) "/" "{name}"'.encode() for name in self.server.folders if name.startswith(prefix)])
    # end def

    async def uid_search(self, *criteria: str, charset: str | None = "utf-8") -> Response:
        self.log(f"UID SEARCH {' '.join(criteria)}")
        self.require_selected("SEARCH")
        assert self.selected is not None
        messages = self.folder(self.selected).messages
        if criteria and criteria[0].startswith("UID "):
            start = int(criteria[0].removeprefix("UID ").split(":")[0])
            found = [m.uid for m in messages if m.uid >= start] or ([max(m.uid for m in messages)] if messages else [])
        else:
            found = [m.uid for m in messages]
        # end if
        return Response("OK", [("SEARCH " + " ".join(str(uid) for uid in found)).encode(), b"Search completed."])
    # end def

    async def uid(self, command: str, *criteria: str) -> Response:
        name = command.lower()
        if name == "fetch":
            return self.uid_fetch(*criteria)
        # end if
        assert name in {"store", "copy", "move", "expunge"}, f"unsupported command {command}"
        self.log(f"UID {command.upper()} {' '.join(criteria)}")
        self.require_selected("UID")
        if not self.writable:
            return Response("NO", [b"[READ-ONLY] mailbox is examined"])
        # end if
        assert self.selected is not None
        source = self.folder(self.selected)
        uid = int(criteria[0])
        message = next((m for m in source.messages if m.uid == uid), None)
        if message is None:
            return Response("OK", [b"nothing to do"])
        # end if
        if name == "store":
            self.store(source, message, criteria[1], criteria[2])
        elif name == "expunge":
            if "UIDPLUS" not in self.server.capabilities:
                return Response("BAD", [b"UID EXPUNGE needs UIDPLUS"])
            # end if
            if "\\Deleted" in message.flags.split():
                source.messages.remove(message)
            # end if
        else:
            target = self.folder(criteria[1])
            copy = FakeMessage(uid=max([m.uid for m in target.messages], default=0) + 1, raw=message.raw, flags=message.flags, body=message.body)
            target.modseq += 1
            copy.modseq = target.modseq
            target.messages.append(copy)
            if name == "move":
                source.messages.remove(message)
            # end if
        # end if
        return Response("OK", [b"done"])
    # end def

    def store(self, folder: FakeFolder, message: FakeMessage, mode: str, flags: str) -> None:
        wanted = flags.strip("()").split()
        current = message.flags.split()
        if mode.startswith("+"):
            current += [flag for flag in wanted if flag not in current]
        elif mode.startswith("-"):
            current = [flag for flag in current if flag not in wanted]
        else:
            current = wanted
        # end if
        folder.modseq += 1
        message.flags, message.modseq = " ".join(current), folder.modseq
    # end def

    def uid_fetch(self, uid_set: str, fields: str) -> Response:
        self.log(f"UID FETCH {uid_set} {fields}")
        self.require_selected("UID")
        assert self.selected is not None
        wanted = {int(uid) for uid in uid_set.split(",")} if uid_set != "1:*" else None
        since = re.search(r"CHANGEDSINCE (\d+)", fields)
        lines: list[bytes | bytearray] = []
        for message in self.folder(self.selected).messages:
            if wanted is not None and message.uid not in wanted:
                continue
            # end if
            if since and message.modseq <= int(since.group(1)):
                continue
            # end if
            lines += fetch_lines(message, fields)
        # end for
        return Response("OK", [*lines, b"Fetch completed."])
    # end def

    async def noop(self) -> Response:
        return Response("OK", [])
    # end def

    async def idle_start(self, timeout: float = 0) -> object:
        self.log("IDLE")
        self.require_selected("IDLE")
        self.idle = True
        return None
    # end def

    async def wait_server_push(self, timeout: float = 0) -> Response:
        return await asyncio.wait_for(self.queue.get(), timeout=timeout)
    # end def

    def idle_done(self) -> None:
        self.log("DONE")
        self.idle = False
    # end def

    def has_pending_idle(self) -> bool:
        return self.idle
    # end def
# end class
