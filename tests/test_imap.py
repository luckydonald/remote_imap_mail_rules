import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from pydantic_settings import SettingsConfigDict

from remote_imap_mail_rules.config import ImapSettings
from remote_imap_mail_rules.imap.bodystructure import parse_parts
from remote_imap_mail_rules.imap.client import ImapClient, ImapError, decode_part
from remote_imap_mail_rules.imap.fetch import parse_fetch, parse_folder_state, parse_list
from remote_imap_mail_rules.imap.models import ChangeKind
from remote_imap_mail_rules.imap.watcher import watch

from .fake_imap import FakeFolder, FakeServer

ACCOUNT = UUID("6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11")


def make_settings(**overrides: object) -> ImapSettings:
    values = dict(
        imap_account_id=ACCOUNT, imap_host="x", imap_username="u", imap_password="p", imap_page_size=2, imap_poll_interval=0.01
    )
    values.update(overrides)
    return ImapSettings(_env_file=None, **values)  # type: ignore[arg-type]
# end def


def test_parse_fetch_with_literals() -> None:
    lines = [
        b'1 FETCH (UID 5 FLAGS (\\Seen $x) INTERNALDATE "26-Oct-2026 08:01:00 +0000" RFC822.SIZE 99 MODSEQ (77) BODY[HEADER] {16}',
        bytearray(b"Subject: hi\r\n\r\n"),
        b" BODY[1] {3}",
        bytearray(b"abc"),
        b")",
        b"Fetch completed.",
    ]
    [message] = parse_fetch(lines)
    assert (message.uid, message.size, message.modseq) == (5, 99, 77)
    assert message.flags == {"\\Seen", "$x"}
    assert message.internaldate is not None and message.internaldate.year == 2026
    assert message.sections == {"HEADER": b"Subject: hi\r\n\r\n", "1": b"abc"}
# end def


def test_parse_state_and_list() -> None:
    state = parse_folder_state([b"OK [UIDVALIDITY 7]", b"OK [UIDNEXT 12]", b"OK [HIGHESTMODSEQ 99]"])
    assert state is not None and (state.uidvalidity, state.uidnext, state.highestmodseq) == (7, 12, 99)
    assert parse_folder_state([b"OK [UIDNEXT 12]"]) is None
    folders = parse_list([b'(\\HasChildren) "/" "INBOX"', b'(\\Noselect) "/" "Foo bar"', b'() NIL Plain'])
    assert [f.name for f in folders] == ["INBOX", "Foo bar", "Plain"]
    assert [f.selectable for f in folders] == [True, False, True]
# end def


def test_bodystructure_attachments() -> None:
    from remote_imap_mail_rules.imap.sexpr import parse

    tree = parse([
        b'((("text" "plain" ("charset" "utf-8") NIL NIL "7bit" 10 1 NIL NIL NIL)("text" "html" NIL NIL NIL "7bit" 20 1 NIL NIL NIL) "alternative")'
        b'("application" "pdf" ("name" "a.pdf") NIL NIL "base64" 300 NIL ("attachment" ("filename" "Invoice.pdf")) NIL)'
        b'("image" "png" NIL NIL NIL "base64" 50 NIL ("inline" ("filename" "l.png")) NIL) "mixed")'
    ])
    parts = parse_parts(tree[0])
    assert [(p.number, p.mime_type) for p in parts] == [
        ("0", "multipart/mixed"), ("1", "multipart/alternative"), ("1.1", "text/plain"), ("1.2", "text/html"), ("2", "application/pdf"), ("3", "image/png"),
    ]
    attachments = [p for p in parts if p.is_attachment]
    assert [(p.filename, p.inline) for p in attachments] == [("Invoice.pdf", False), ("l.png", True)]
# end def


def test_decode_part_transfer_encodings() -> None:
    from remote_imap_mail_rules.imap.bodystructure import Part

    part = Part("1", "text/plain", {"charset": "iso-8859-1"}, "quoted-printable")
    assert (decode_part(part, b"caf=E9") or "").strip() == "café"
    part = Part("1", "text/plain", {"charset": "utf-8"}, "base64")
    assert (decode_part(part, b"aGVsbG8=") or "").strip() == "hello"
# end def


async def test_pages_newest_first_and_readonly() -> None:
    server = FakeServer()
    for uid in range(1, 6):
        server.add("INBOX", uid, f"mail {uid}")
    # end for
    async with ImapClient(make_settings(), lambda settings: server.connect(settings)) as client:
        pages = [page async for page in client.iter_pages(ACCOUNT, "INBOX", 2)]
    # end with
    assert [[m.uid for m in page] for page in pages] == [[5, 4], [3, 2], [1]]
    assert pages[0][0].headers["Subject"] == "mail 5"
    assert pages[0][0].mime_type == "text/plain"
    assert all(not command.startswith(("STORE", "COPY", "MOVE", "EXPUNGE", "SELECT")) for command in server.commands)
    assert any(command.startswith("EXAMINE") for command in server.commands)
# end def


async def test_empty_folder_and_missing_state() -> None:
    server = FakeServer()
    server.folders["INBOX"] = FakeFolder()
    async with ImapClient(make_settings(), lambda settings: server.connect(settings)) as client:
        assert [page async for page in client.iter_pages(ACCOUNT, "INBOX", 2)] == []
        with pytest.raises(KeyError):
            await client.examine("Nope")
        # end with
    # end with
# end def


async def test_fetch_new_and_changed() -> None:
    server = FakeServer()
    server.add("INBOX", 1, "one")
    server.add("INBOX", 2, "two")
    async with ImapClient(make_settings(), lambda settings: server.connect(settings)) as client:
        state = await client.examine("INBOX")
        assert [m.uid for m in await client.fetch_new(ACCOUNT, "INBOX", 2)] == []
        server.add("INBOX", 3, "three")
        assert [m.uid for m in await client.fetch_new(ACCOUNT, "INBOX", 2)] == [3]
        server.set_flags("INBOX", 1, "\\Seen")
        changed = await client.fetch_changed(ACCOUNT, "INBOX", state.highestmodseq or 0)
        assert sorted(m.uid for m in changed) == [1, 3]
        assert next(m for m in changed if m.uid == 1).has_flag("\\Seen")
    # end with
# end def


async def test_lazy_body_loading() -> None:
    server = FakeServer()
    server.add("INBOX", 1, "one")
    async with ImapClient(make_settings(), lambda settings: server.connect(settings)) as client:
        [page] = [p async for p in client.iter_pages(ACCOUNT, "INBOX", 5)]
        assert not any("BODY.PEEK[1]" in command for command in server.commands)
        bodies = await page[0].load_bodies()
        assert bodies.text == "hello"
        assert bodies.html is None
    # end with
# end def


async def test_expand_recursive_folders() -> None:
    server = FakeServer()
    for name in ("Lists", "Lists/a", "Lists/b", "Listsx", "Other"):
        server.add(name, 1, name)
    # end for
    async with ImapClient(make_settings(), lambda settings: server.connect(settings)) as client:
        assert await client.expand_folder("Lists", False) == ["Lists"]
        assert await client.expand_folder("Lists", True) == ["Lists", "Lists/a", "Lists/b"]
        assert await client.expand_folder("Missing", True) == []
    # end with
# end def


async def test_not_connected() -> None:
    client = ImapClient(make_settings(), lambda settings: FakeServer().connect(settings))
    with pytest.raises(ImapError):
        await client.examine("INBOX")
    # end with
# end def


async def test_watch_uses_idle_push() -> None:
    server = FakeServer()
    server.add("INBOX", 1, "one")
    async with ImapClient(make_settings(), lambda settings: server.connect(settings)) as client:
        await client.examine("INBOX")
        events = watch(client, "INBOX", poll_interval=0.01, idle_timeout=5)
        waiting = asyncio.create_task(anext(events))
        await asyncio.sleep(0.01)
        server.push()
        event = await asyncio.wait_for(waiting, 1)
        assert event.kind == ChangeKind.push
        assert "IDLE" in server.commands and "DONE" in server.commands
        await events.aclose()
    # end with
# end def


async def test_watch_renews_idle_after_timeout() -> None:
    server = FakeServer()
    server.add("INBOX", 1, "one")
    async with ImapClient(make_settings(), lambda settings: server.connect(settings)) as client:
        await client.examine("INBOX")
        events = watch(client, "INBOX", poll_interval=0.01, idle_timeout=0.02)
        waiting = asyncio.create_task(anext(events))
        await asyncio.sleep(0.1)
        server.push()
        await asyncio.wait_for(waiting, 1)
        assert server.commands.count("IDLE") >= 2
        await events.aclose()
    # end with
# end def


async def test_watch_reports_when_the_next_poll_is_due() -> None:
    server = FakeServer(capabilities={"IMAP4REV1"})
    server.add("INBOX", 1, "one")
    due: list[datetime | None] = []
    async with ImapClient(make_settings(), lambda settings: server.connect(settings)) as client:
        await client.examine("INBOX")
        before = datetime.now(UTC)
        events = watch(client, "INBOX", poll_interval=0.05, on_schedule=due.append)
        await asyncio.wait_for(anext(events), 1)
        await events.aclose()
    # end with
    assert len(due) == 1
    planned = due[0]
    assert planned is not None
    assert before + timedelta(seconds=0.05) <= planned <= datetime.now(UTC) + timedelta(seconds=0.05)
# end def


async def test_watch_reports_no_due_time_while_in_idle() -> None:
    server = FakeServer()
    server.add("INBOX", 1, "one")
    due: list[datetime | None] = []
    async with ImapClient(make_settings(), lambda settings: server.connect(settings)) as client:
        await client.examine("INBOX")
        events = watch(client, "INBOX", poll_interval=0.01, idle_timeout=5, on_schedule=due.append)
        waiting = asyncio.create_task(anext(events))
        await asyncio.sleep(0.01)
        assert due == [None]
        server.push()
        await asyncio.wait_for(waiting, 1)
        await events.aclose()
    # end with
# end def


async def test_watch_falls_back_to_polling_without_idle() -> None:
    server = FakeServer(capabilities={"IMAP4REV1"})
    server.add("INBOX", 1, "one")
    async with ImapClient(make_settings(), lambda settings: server.connect(settings)) as client:
        await client.examine("INBOX")
        events = watch(client, "INBOX", poll_interval=0.01)
        first, second = await asyncio.wait_for(anext(events), 1), await asyncio.wait_for(anext(events), 1)
        assert first.kind == second.kind == ChangeKind.poll
        assert "IDLE" not in server.commands
        await events.aclose()
    # end with
# end def
