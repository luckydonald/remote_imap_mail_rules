"""The IMAP pieces behind the mail browser: counts, random access pages, single messages, parts and folder names."""

import base64

from remote_imap_mail_rules.imap.client import ImapClient
from remote_imap_mail_rules.imap.fetch import parse_list
from remote_imap_mail_rules.imap.transfer import decode_transfer
from remote_imap_mail_rules.imap.utf7 import decode_folder_name

from .fake_imap import FakeServer
from .test_imap import ACCOUNT, make_settings

PNG = b"\x89PNG\r\n\x1a\nbytes"
STRUCTURE = (
    '(("text" "plain" ("charset" "utf-8") NIL NIL "7bit" 5 1 NIL NIL NIL)'
    f' ("image" "png" ("name" "logo.png") "<logo@x>" NIL "base64" {len(PNG)} NIL ("attachment" ("filename" "logo.png")) NIL) "mixed")'
)


def client_for(server: FakeServer) -> ImapClient:
    return ImapClient(make_settings(), lambda settings: server.connect(settings))
# end def


async def test_folder_counts() -> None:
    server = FakeServer()
    server.add("INBOX", 1, "one", flags="\\Seen")
    server.add("INBOX", 2, "two")
    server.add("INBOX", 3, "three")
    async with client_for(server) as client:
        counts = await client.folder_counts("INBOX")
    # end with
    assert (counts.messages, counts.unseen) == (3, 2)
    assert not any(command.startswith("EXAMINE") for command in server.commands)
# end def


async def test_list_page_cursor_and_total() -> None:
    server = FakeServer()
    for uid in range(1, 8):
        server.add("INBOX", uid, f"mail {uid}")
    # end for
    async with client_for(server) as client:
        first, total = await client.list_page(ACCOUNT, "INBOX", 3)
        second, _ = await client.list_page(ACCOUNT, "INBOX", 3, before_uid=first[-1].uid)
        last, _ = await client.list_page(ACCOUNT, "INBOX", 3, before_uid=second[-1].uid)
        none, _ = await client.list_page(ACCOUNT, "INBOX", 3, before_uid=last[-1].uid)
    # end with
    assert total == 7
    assert [m.uid for m in first] == [7, 6, 5]
    assert [m.uid for m in second] == [4, 3, 2]
    assert [m.uid for m in last] == [1]
    assert none == []
# end def


async def test_fetch_message_and_part() -> None:
    server = FakeServer()
    message = server.add("INBOX", 1, "with logo")
    message.structure = STRUCTURE
    message.parts = {"2": base64.b64encode(PNG)}
    async with client_for(server) as client:
        mail = await client.fetch_message(ACCOUNT, "INBOX", 1)
        assert mail is not None
        [attachment] = mail.attachments
        assert (attachment.part, attachment.content_id, attachment.filename) == ("2", "logo@x", "logo.png")
        found = await client.fetch_part("INBOX", 1, "2")
        assert found is not None
        part, data = found
        assert part.mime_type == "image/png"
        assert data == PNG
        assert await client.fetch_part("INBOX", 1, "9") is None
        assert await client.fetch_part("INBOX", 1, "0") is None
        assert await client.fetch_message(ACCOUNT, "INBOX", 99) is None
    # end with
    assert all(command.startswith(("LOGIN", "LOGOUT", "EXAMINE", "STATUS", "UID FETCH", "UID SEARCH")) for command in server.commands)
# end def


def test_special_use_and_names() -> None:
    lines = [
        b'() "/" "INBOX"',
        b'(\\Sent) "/" "Gesendet"',
        b'(\\Trash \\HasNoChildren) "/" "Papierkorb"',
        b'() "/" "Plain"',
    ]
    uses = {info.name: info.special_use for info in parse_list(lines)}
    assert uses == {"INBOX": "inbox", "Gesendet": "sent", "Papierkorb": "trash", "Plain": None}
    assert decode_folder_name("Entw&APw-rfe") == "Entwürfe"
    assert decode_folder_name("A &- B") == "A & B"
    assert decode_folder_name("INBOX/Plain") == "INBOX/Plain"
# end def


def test_decode_transfer() -> None:
    assert decode_transfer("base64", base64.b64encode(b"abc\x00")) == b"abc\x00"
    assert decode_transfer("quoted-printable", b"caf=C3=A9") == "café".encode()
    assert decode_transfer("7bit", b"raw") == b"raw"
    assert decode_transfer(None, b"raw") == b"raw"
# end def
