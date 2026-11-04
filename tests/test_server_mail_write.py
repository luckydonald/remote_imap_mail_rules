"""The write routes of the mail browser: flags and move, only with `ACTIONS_ENABLED`."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from remote_imap_mail_rules.server.app import create_app
from remote_imap_mail_rules.server.auth import SESSION_COOKIE, make_session_token
from remote_imap_mail_rules.server.settings import ServerSettings
from tests.fake_imap import FakeServer
from tests.test_server_accounts import BODY, KEY
from tests.test_server_mail import server  # noqa: F401  (fixture)


def make_client(tmp_path: Path, server: FakeServer, actions_enabled: bool) -> Iterator[TestClient]:
    settings = ServerSettings(
        _env_file=None, rules_path=None, database_url=f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite3'}", frontend_dist=tmp_path / "missing",
        secret_key=SecretStr(KEY), admin_username="admin", admin_password=SecretStr("admin-secret"), watch_enabled=False, actions_enabled=actions_enabled,
    )
    with TestClient(create_app(settings, None, lambda imap_settings: server.connect(imap_settings))) as test_client:
        test_client.cookies.set(SESSION_COOKIE, make_session_token(settings))
        yield test_client
    # end with
# end def


@pytest.fixture
def enabled(tmp_path: Path, server: FakeServer) -> Iterator[TestClient]:  # noqa: F811
    yield from make_client(tmp_path, server, True)
# end def


@pytest.fixture
def disabled(tmp_path: Path, server: FakeServer) -> Iterator[TestClient]:  # noqa: F811
    yield from make_client(tmp_path, server, False)
# end def


def test_flags_are_refused_while_actions_are_off(disabled: TestClient, server: FakeServer) -> None:  # noqa: F811
    account = disabled.post("/api/accounts", json=BODY).json()["id"]
    response = disabled.post(f"/api/mail/accounts/{account}/messages/3/flags", json={"add": ["\\Seen"]})
    assert (response.status_code, response.json()["detail"]) == (409, "actions_disabled")
    assert not any(command.startswith(("SELECT", "UID STORE")) for command in server.commands)
# end def


def test_flags_mark_read_and_unread(enabled: TestClient, server: FakeServer) -> None:  # noqa: F811
    account = enabled.post("/api/accounts", json=BODY).json()["id"]
    assert enabled.post(f"/api/mail/accounts/{account}/messages/3/flags", json={"add": ["\\Seen"]}).status_code == 204
    assert enabled.get(f"/api/mail/accounts/{account}/messages/3").json()["seen"] is True
    assert enabled.post(f"/api/mail/accounts/{account}/messages/3/flags", json={"remove": ["\\Seen"]}).status_code == 204
    assert enabled.get(f"/api/mail/accounts/{account}/messages/3").json()["seen"] is False
    assert any(command.startswith("SELECT") for command in server.commands)
# end def


def test_flags_allow_only_a_few_system_flags(enabled: TestClient) -> None:
    account = enabled.post("/api/accounts", json=BODY).json()["id"]
    response = enabled.post(f"/api/mail/accounts/{account}/messages/3/flags", json={"add": ["\\Deleted"]})
    assert response.status_code == 422
# end def


def test_move_to_another_folder(enabled: TestClient, server: FakeServer) -> None:  # noqa: F811
    server.capabilities |= {"MOVE", "UIDPLUS"}
    account = enabled.post("/api/accounts", json=BODY).json()["id"]
    response = enabled.post(f"/api/mail/accounts/{account}/messages/3/move", json={"folder": "Sent"})
    assert response.status_code == 200
    assert response.json()["folder"] == "Sent"
    assert 3 not in [mail.uid for mail in server.folders["INBOX"].messages]
    assert enabled.post(f"/api/mail/accounts/{account}/messages/4/move", json={"folder": "INBOX"}).status_code == 422
# end def


def test_move_is_refused_while_actions_are_off(disabled: TestClient) -> None:
    account = disabled.post("/api/accounts", json=BODY).json()["id"]
    assert disabled.post(f"/api/mail/accounts/{account}/messages/3/move", json={"folder": "Sent"}).status_code == 409
# end def
