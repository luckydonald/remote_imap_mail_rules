"""The mail browser API against the fake IMAP server."""

import base64
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from remote_imap_mail_rules.config import ImapSettings
from remote_imap_mail_rules.imap.connection import ImapConnection
from remote_imap_mail_rules.server.app import create_app
from remote_imap_mail_rules.server.auth import SESSION_COOKIE, make_session_token
from remote_imap_mail_rules.server.settings import ServerSettings
from tests.fake_imap import FakeServer
from tests.test_server_accounts import BODY, KEY

PNG = b"\x89PNG\r\n\x1a\nbytes"
TEXT = b"Hello plain"
HTML = (
    b'<p onclick="x()">Hello <b>html</b></p><script>alert(1)</script>'
    b'<img src="cid:logo@x"><img src="https://tracker.example/p.gif"><a href="javascript:evil()">bad</a>'
)
EVIL = b"<script>alert(1)</script>"
STRUCTURE = (
    f'(("text" "plain" ("charset" "utf-8") NIL NIL "7bit" {len(TEXT)} 1 NIL NIL NIL)'
    f' ("text" "html" ("charset" "utf-8") NIL NIL "7bit" {len(HTML)} 1 NIL NIL NIL)'
    f' ("image" "png" ("name" "logo.png") "<logo@x>" NIL "base64" {len(PNG)} NIL ("inline" ("filename" "logo.png")) NIL)'
    f' ("text" "html" ("name" "evil.html") NIL NIL "7bit" {len(EVIL)} 1 NIL ("attachment" ("filename" "evil.html")) NIL) "mixed")'
)


@pytest.fixture
def server() -> FakeServer:
    fake = FakeServer()
    fake.attributes = {"Sent": "\\Sent", "Entw&APw-rfe": "\\Drafts"}
    for uid in range(1, 6):
        fake.add("INBOX", uid, f"mail {uid}", flags="\\Seen" if uid < 3 else "", sender='"Max Muster" <max@example.com>')
    # end for
    rich = fake.add("INBOX", 6, "Rich", sender="=?utf-8?q?J=C3=BCrgen?= <j@example.com>")
    rich.structure = STRUCTURE
    rich.parts = {"1": TEXT, "2": HTML, "3": base64.b64encode(PNG), "4": EVIL}
    fake.add("Sent", 1, "sent one")
    fake.add("Entw&APw-rfe", 1, "draft one")
    return fake
# end def


@pytest.fixture
def client(tmp_path: Path, server: FakeServer) -> Iterator[TestClient]:
    settings = ServerSettings(
        _env_file=None,
        rules_path=None,
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite3'}",
        frontend_dist=tmp_path / "missing",
        secret_key=SecretStr(KEY),
    )
    with TestClient(create_app(settings, None, lambda imap_settings: server.connect(imap_settings))) as test_client:
        test_client.cookies.set(SESSION_COOKIE, make_session_token(settings))
        yield test_client
    # end with
# end def


@pytest.fixture
def account_id(client: TestClient) -> str:
    return str(client.post("/api/accounts", json=BODY).json()["id"])
# end def


def test_mail_needs_login(client: TestClient, account_id: str) -> None:
    client.cookies.clear()
    assert client.get(f"/api/mail/accounts/{account_id}/folders").status_code == 401
# end def


def test_folders_with_counts_and_names(client: TestClient, account_id: str) -> None:
    folders = {folder["name"]: folder for folder in client.get(f"/api/mail/accounts/{account_id}/folders").json()}
    assert folders["INBOX"]["special_use"] == "inbox"
    assert (folders["INBOX"]["messages"], folders["INBOX"]["unseen"]) == (6, 4)
    assert folders["Sent"]["special_use"] == "sent"
    assert folders["Entw&APw-rfe"]["display_name"] == "Entwürfe"
    assert folders["Entw&APw-rfe"]["special_use"] == "drafts"
# end def


def test_paging_with_cursor(client: TestClient, account_id: str) -> None:
    url = f"/api/mail/accounts/{account_id}/messages"
    first = client.get(url, params={"folder": "INBOX", "limit": 4}).json()
    assert [m["uid"] for m in first["messages"]] == [6, 5, 4, 3]
    assert first["total"] == 6 and first["next_before_uid"] == 3
    second = client.get(url, params={"folder": "INBOX", "limit": 4, "before_uid": first["next_before_uid"]}).json()
    assert [m["uid"] for m in second["messages"]] == [2, 1]
    assert second["next_before_uid"] is None
    summary = second["messages"][0]
    assert summary["sender"] == {"name": "Max Muster", "address": "max@example.com"}
    assert (summary["subject"], summary["seen"], summary["has_attachments"]) == ("mail 2", True, False)
    assert client.get(url, params={"limit": 0}).status_code == 422
# end def


def test_message_is_sanitized_and_cid_resolved(client: TestClient, account_id: str) -> None:
    detail = client.get(f"/api/mail/accounts/{account_id}/messages/6", params={"folder": "INBOX"}).json()
    assert detail["sender"]["name"] == "Jürgen"
    assert detail["text"] == "Hello plain"
    html = detail["html"]
    assert "<b>html</b>" in html
    assert "script" not in html and "onclick" not in html and "javascript:" not in html and "tracker.example" not in html
    logo = next(a for a in detail["attachments"] if a["content_id"] == "logo@x")
    assert f'src="{logo["url"]}"' in html
    assert [a["filename"] for a in detail["attachments"]] == ["logo.png", "evil.html"]
    assert detail["has_attachments"] is True
# end def


def test_parts_are_served_safely(client: TestClient, account_id: str) -> None:
    base = f"/api/mail/accounts/{account_id}/messages/6/parts"
    logo = client.get(f"{base}/3", params={"folder": "INBOX"})
    assert logo.content == PNG and logo.headers["content-type"] == "image/png"
    assert logo.headers["content-disposition"].startswith("inline")
    evil = client.get(f"{base}/4", params={"folder": "INBOX"})
    assert evil.headers["content-disposition"].startswith("attachment")
    assert evil.headers["x-content-type-options"] == "nosniff"
    assert evil.headers["content-security-policy"].startswith("sandbox")
    assert client.get(f"{base}/9", params={"folder": "INBOX"}).status_code == 404
# end def


def test_not_found(client: TestClient, account_id: str) -> None:
    assert client.get(f"/api/mail/accounts/{account_id}/messages/99").status_code == 404
    assert client.get("/api/mail/accounts/6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11/folders").status_code == 404
# end def


def test_everything_is_read_only(client: TestClient, server: FakeServer, account_id: str) -> None:
    client.get(f"/api/mail/accounts/{account_id}/folders")
    client.get(f"/api/mail/accounts/{account_id}/messages/6")
    client.get(f"/api/mail/accounts/{account_id}/messages/6/parts/3")
    allowed = ("LOGIN", "LOGOUT", "LIST", "STATUS", "EXAMINE", "UID FETCH", "UID SEARCH")
    assert server.commands and all(command.startswith(allowed) for command in server.commands)
# end def


@pytest.mark.parametrize(("error", "status"), [(OSError("down"), 502), (TimeoutError(), 504)])
def test_imap_failures(tmp_path: Path, error: Exception, status: int) -> None:
    settings = ServerSettings(
        _env_file=None, rules_path=None, database_url=f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite3'}", frontend_dist=tmp_path / "missing", secret_key=SecretStr(KEY)
    )

    def broken(imap_settings: ImapSettings) -> ImapConnection:
        raise error
    # end def

    with TestClient(create_app(settings, None, broken)) as client:
        client.cookies.set(SESSION_COOKIE, make_session_token(settings))
        account = client.post("/api/accounts", json=BODY).json()["id"]
        assert client.get(f"/api/mail/accounts/{account}/folders").status_code == status
    # end with
# end def
