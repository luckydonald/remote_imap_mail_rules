import pytest

from remote_imap_mail_rules.imap.client import ImapClient, ImapError
from remote_imap_mail_rules.imap.models import RawMessage

from .fake_imap import FakeFolder, FakeServer
from .test_imap import make_settings


def make_server(capabilities: set[str]) -> FakeServer:
    server = FakeServer(capabilities)
    server.add("INBOX", 1, "one", flags="\\Seen")
    server.add("INBOX", 2, "two")
    server.add("Archive", 7, "old")
    return server
# end def


def flags(server: FakeServer, folder: str, uid: int) -> set[str]:
    return set(next(m for m in server.folders[folder].messages if m.uid == uid).flags.split())
# end def


async def test_store_flags_selects_the_folder() -> None:
    server = make_server({"IMAP4REV1", "CONDSTORE"})
    async with ImapClient(make_settings(), server.connect) as client:
        await client.store_flags("INBOX", 2, add=("\\Seen", "\\Flagged", "Todo"))
        await client.store_flags("INBOX", 1, remove=("\\Seen",))
    assert flags(server, "INBOX", 2) == {"\\Seen", "\\Flagged", "Todo"}
    assert flags(server, "INBOX", 1) == set()
    assert 'SELECT "INBOX"' in server.commands and not any(c.startswith("EXAMINE") for c in server.commands)
# end def


async def test_examine_makes_the_folder_read_only_again() -> None:
    server = make_server({"IMAP4REV1"})
    async with ImapClient(make_settings(), server.connect) as client:
        await client.select("INBOX")
        assert client.writable is True
        await client.examine("INBOX")
        assert client.writable is False
        await client.store_flags("INBOX", 2, add=("\\Seen",))  # reselects on its own
        assert client.writable is True
    assert flags(server, "INBOX", 2) == {"\\Seen"}
# end def


async def test_move_with_the_move_capability() -> None:
    server = make_server({"IMAP4REV1", "MOVE"})
    async with ImapClient(make_settings(), server.connect) as client:
        await client.move("INBOX", 2, "Archive")
    assert [m.uid for m in server.folders["INBOX"].messages] == [1]
    assert [m.uid for m in server.folders["Archive"].messages] == [7, 8]
    assert "UID MOVE 2 \"Archive\"" in server.commands
# end def


async def test_move_falls_back_to_copy_and_uid_expunge() -> None:
    server = make_server({"IMAP4REV1", "UIDPLUS"})
    server.folders["INBOX"].messages[0].flags = "\\Deleted"  # someone else's pending delete must survive
    async with ImapClient(make_settings(), server.connect) as client:
        await client.move("INBOX", 2, "Archive")
    assert [m.uid for m in server.folders["INBOX"].messages] == [1]
    assert [m.uid for m in server.folders["Archive"].messages] == [7, 8]
    assert any(c.startswith("UID EXPUNGE 2") for c in server.commands)
# end def


async def test_move_refuses_without_move_and_uidplus() -> None:
    server = make_server({"IMAP4REV1"})
    async with ImapClient(make_settings(), server.connect) as client:
        with pytest.raises(ImapError):
            await client.move("INBOX", 2, "Archive")
    assert not any("EXPUNGE" in c or "COPY" in c for c in server.commands)
    assert [m.uid for m in server.folders["INBOX"].messages] == [1, 2]
# end def


async def test_move_reports_the_new_uid_with_uidplus() -> None:
    server = make_server({"IMAP4REV1", "UIDPLUS"})
    async with ImapClient(make_settings(), server.connect) as client:
        moved = await client.move("INBOX", 2, "Archive")
    assert (moved.folder, moved.uid, moved.uidvalidity) == ("Archive", 8, 1)
# end def


async def test_move_without_uidplus_has_no_uid() -> None:
    server = make_server({"IMAP4REV1", "MOVE"})
    async with ImapClient(make_settings(), server.connect) as client:
        moved = await client.move("INBOX", 2, "Archive")
    assert moved.uid is None and moved.folder == "Archive"
# end def


async def test_delete_expunges_only_that_uid() -> None:
    server = make_server({"IMAP4REV1", "UIDPLUS"})
    server.folders["INBOX"].messages[0].flags = "\\Deleted"
    async with ImapClient(make_settings(), server.connect) as client:
        await client.delete("INBOX", 2)
    assert [m.uid for m in server.folders["INBOX"].messages] == [1]
    assert any(c.startswith("UID EXPUNGE 2") for c in server.commands)
# end def


async def test_delete_refuses_without_uidplus() -> None:
    server = make_server({"IMAP4REV1"})
    async with ImapClient(make_settings(), server.connect) as client:
        with pytest.raises(ImapError):
            await client.delete("INBOX", 2)
    assert [m.uid for m in server.folders["INBOX"].messages] == [1, 2]
# end def


async def test_fetch_raw_then_append_copies_the_whole_mail() -> None:
    source = make_server({"IMAP4REV1"})
    source.folders["INBOX"].messages[1].body = b"the body"
    target = FakeServer({"IMAP4REV1", "UIDPLUS"})
    target.folders["INBOX"] = FakeFolder(uidvalidity=5)
    async with ImapClient(make_settings(), source.connect) as reader, ImapClient(make_settings(), target.connect) as writer:
        message = await reader.fetch_raw("INBOX", 2)
        assert message is not None
        moved = await writer.append("INBOX", message)
    assert (moved.folder, moved.uid, moved.uidvalidity) == ("INBOX", 1, 5)
    copy = target.folders["INBOX"].messages[0]
    assert copy.raw + copy.body == source.folders["INBOX"].messages[1].raw + b"the body"
    assert not any("STORE" in c or "EXPUNGE" in c for c in source.commands), "reading never changes the source"
    assert [m.uid for m in source.folders["INBOX"].messages] == [1, 2]
# end def


async def test_append_keeps_flags_but_not_recent() -> None:
    target = FakeServer({"IMAP4REV1"})
    target.folders["INBOX"] = FakeFolder()
    async with ImapClient(make_settings(), target.connect) as client:
        await client.append("INBOX", RawMessage(uid=1, raw=b"Subject: x\r\n\r\nhi", flags=frozenset({"\\Seen", "\\Recent", "Todo"}), internaldate=None))
    assert set(target.folders["INBOX"].messages[0].flags.split()) == {"\\Seen", "Todo"}
# end def


async def test_fetch_raw_of_a_missing_uid_is_none() -> None:
    server = make_server({"IMAP4REV1"})
    async with ImapClient(make_settings(), server.connect) as client:
        assert await client.fetch_raw("INBOX", 99) is None
# end def


async def test_find_message_id() -> None:
    server = make_server({"IMAP4REV1"})
    server.add("INBOX", 3, "three", message_id="<abc@example.com>")
    async with ImapClient(make_settings(), server.connect) as client:
        assert await client.find_message_id("INBOX", "<abc@example.com>") == 3
        assert await client.find_message_id("INBOX", "<other@example.com>") is None
# end def


def make_dovecot() -> FakeServer:
    """Folders live under `INBOX.` with `.` as delimiter, like Dovecot with a namespace prefix."""
    server = FakeServer({"IMAP4REV1", "MOVE", "UIDPLUS"})
    server.delimiter = "."
    server.add("INBOX", 1, "one")
    server.folders["INBOX.Boxed in.Updates"] = FakeFolder()
    return server
# end def


async def test_resolve_folder_maps_slashes_prefix_and_case() -> None:
    server = make_dovecot()
    async with ImapClient(make_settings(), server.connect) as client:
        assert await client.resolve_folder("Boxed In/Updates") == "INBOX.Boxed in.Updates"
        assert await client.resolve_folder("INBOX.Boxed in.Updates") == "INBOX.Boxed in.Updates"
        assert await client.resolve_folder("INBOX") == "INBOX"
        assert await client.resolve_folder("Boxed In/New") == "INBOX.Boxed In.New"
# end def


async def test_resolve_folder_keeps_slash_servers() -> None:
    server = make_server({"IMAP4REV1"})
    async with ImapClient(make_settings(), server.connect) as client:
        assert await client.resolve_folder("Archive") == "Archive"
        assert await client.resolve_folder("Boxed In/Updates") == "Boxed In/Updates"
# end def


async def test_move_uses_the_resolved_name() -> None:
    server = make_dovecot()
    async with ImapClient(make_settings(), server.connect) as client:
        await client.move("INBOX", 1, "Boxed In/Updates")
    assert [m.uid for m in server.folders["INBOX.Boxed in.Updates"].messages] == [1]
    assert 'UID MOVE 1 "INBOX.Boxed in.Updates"' in server.commands
# end def
