import pytest

from remote_imap_mail_rules.imap.client import ImapClient, ImapError

from .fake_imap import FakeServer
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
