"""The accounts API and the seeding from the environment."""

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text

from aioimaplib import Response

from remote_imap_mail_rules.config import ImapSettings
from remote_imap_mail_rules.imap.client import ConnectionFactory
from remote_imap_mail_rules.imap.connection import ImapConnection
from remote_imap_mail_rules.server.app import create_app
from remote_imap_mail_rules.server.auth import SESSION_COOKIE, make_session_token
from remote_imap_mail_rules.server.settings import ServerSettings
from tests.conftest import ACCOUNT_ID
from tests.fake_imap import FakeServer
from tests.settings import TestImapSettings

KEY = Fernet.generate_key().decode()
BODY = {"name": "Work", "host": "imap.work.example", "port": 993, "ssl": True, "username": "me@work.example", "password": "secret"}


def make_client(tmp_path: Path, key: str | None = KEY, env: TestImapSettings | None = None, factory: ConnectionFactory | None = None) -> TestClient:
    settings = ServerSettings(
        _env_file=None,
        rules_path=tmp_path / "rules.yml",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite3'}",
        frontend_dist=tmp_path / "missing",
        secret_key=SecretStr(key) if key else None, admin_username="admin", admin_password=SecretStr("admin-secret"),
    )
    client = TestClient(create_app(settings, env) if factory is None else create_app(settings, env, factory))
    if key:
        client.cookies.set(SESSION_COOKIE, make_session_token(settings))
    # end if
    return client
# end def


def make_env(**overrides: object) -> TestImapSettings:
    values: dict[str, object] = dict(
        imap_account_id=ACCOUNT_ID, imap_account_name="Private", imap_host="imap.example.com", imap_username="me@example.com", imap_password="secret"
    )
    values.update(overrides)
    return TestImapSettings(_env_file=None, **values)  # type: ignore[arg-type]
# end def


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    with make_client(tmp_path) as test_client:
        yield test_client
    # end with
# end def


def test_crud_and_no_password_leak(client: TestClient, tmp_path: Path) -> None:
    created = client.post("/api/accounts", json=BODY)
    assert created.status_code == 201
    data = created.json()
    assert "password" not in data and data["has_password"] is True
    account_id = data["id"]
    assert [a["id"] for a in client.get("/api/accounts").json()] == [account_id]

    updated = client.put(f"/api/accounts/{account_id}", json={**BODY, "name": "Renamed", "password": None})
    assert updated.json()["name"] == "Renamed" and updated.json()["id"] == account_id

    # The password is encrypted in the database.
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite3'}")
    with engine.connect() as connection:
        stored = connection.execute(text("select password_encrypted from accounts")).scalar_one()
    # end with
    engine.dispose()
    assert "secret" not in stored

    assert client.delete(f"/api/accounts/{account_id}").status_code == 204
    assert client.get(f"/api/accounts/{account_id}").status_code == 404
    assert client.get("/api/accounts").json() == []
# end def


def test_validation(client: TestClient) -> None:
    assert client.post("/api/accounts", json={**BODY, "port": 0}).status_code == 422
    assert client.post("/api/accounts", json={**BODY, "password": ""}).status_code == 422
# end def


def test_no_secret_key_is_503(tmp_path: Path) -> None:
    with make_client(tmp_path, key=None) as client:
        assert client.post("/api/accounts", json=BODY).status_code == 503
    # end with
# end def


def test_seeded_from_env_and_not_overwritten(tmp_path: Path) -> None:
    with make_client(tmp_path, env=make_env()) as client:
        accounts = client.get("/api/accounts").json()
        assert [a["id"] for a in accounts] == [str(ACCOUNT_ID)]
        assert accounts[0]["name"] == "Private" and accounts[0]["env_differs"] == []
        client.put(f"/api/accounts/{ACCOUNT_ID}", json={**BODY, "password": None})
    # end with
    # A restart with the same environment keeps the edit and reports the difference, never the values.
    with make_client(tmp_path, env=make_env()) as client:
        account = client.get(f"/api/accounts/{ACCOUNT_ID}").json()
        assert account["name"] == "Work"
        assert set(account["env_differs"]) == {"host", "username"}
    # end with
# end def


def test_changed_env_password_is_reported(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    with make_client(tmp_path, env=make_env()):
        pass
    # end with
    with caplog.at_level(logging.WARNING), make_client(tmp_path, env=make_env(imap_password="new-secret")) as client:
        assert client.get(f"/api/accounts/{ACCOUNT_ID}").json()["env_differs"] == ["password"]
    # end with
    assert "password" in caplog.text and "new-secret" not in caplog.text
# end def


def test_seeding_skipped_without_key(tmp_path: Path) -> None:
    with make_client(tmp_path, key=None, env=make_env()) as client:
        assert client.get("/api/accounts").status_code == 503
    # end with
    with make_client(tmp_path) as client:
        assert client.get("/api/accounts").json() == []
    # end with
# end def


NEW_ID = "11111111-2222-4333-8444-555555555555"

RULES = f"""\
rules:
  - name: Move it  # keep this comment
    locations:
      - account_id: {ACCOUNT_ID}
    when:
      type: text
      field: account_id
      operator: equals
      value: {ACCOUNT_ID}
    actions:
      - type: move
        folder: Archive
        account_id: {ACCOUNT_ID}
"""


def test_create_with_id_and_duplicate(client: TestClient) -> None:
    created = client.post("/api/accounts", json={**BODY, "id": NEW_ID})
    assert created.status_code == 201 and created.json()["id"] == NEW_ID
    assert client.post("/api/accounts", json={**BODY, "id": NEW_ID}).status_code == 409
# end def


def test_change_id_rewrites_the_rules_file(tmp_path: Path) -> None:
    (tmp_path / "rules.yml").write_text(RULES)
    with make_client(tmp_path, env=make_env()) as client:
        same = {**BODY, "host": "imap.example.com", "username": "me@example.com"}
        changed = client.put(f"/api/accounts/{ACCOUNT_ID}", json={**same, "id": NEW_ID, "password": None})
        assert changed.status_code == 200 and changed.json()["id"] == NEW_ID
        assert client.get(f"/api/accounts/{ACCOUNT_ID}").status_code == 404
        text = (tmp_path / "rules.yml").read_text()
        assert text == RULES.replace(str(ACCOUNT_ID), NEW_ID)
        assert "# keep this comment" in text
    # end with
    # A restart does not seed the identical environment account a second time.
    with make_client(tmp_path, env=make_env()) as client:
        assert [a["id"] for a in client.get("/api/accounts").json()] == [NEW_ID]
    # end with
# end def


def test_change_id_to_an_existing_one_is_409(client: TestClient) -> None:
    first = client.post("/api/accounts", json=BODY).json()["id"]
    second = client.post("/api/accounts", json={**BODY, "name": "Other"}).json()["id"]
    assert client.put(f"/api/accounts/{first}", json={**BODY, "id": second, "password": None}).status_code == 409
# end def


def test_mail_events_follow_the_id(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        old = client.post("/api/accounts", json=BODY).json()["id"]
        engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite3'}")
        with engine.begin() as connection:
            connection.exec_driver_sql("PRAGMA foreign_keys=ON")
            connection.execute(
                text("INSERT INTO mail_events (id, account_id, folder, uid, kind, detail, created_at) VALUES (:i, :a, 'INBOX', 1, 'first_seen', '{}', '2026-01-01')"),
                {"i": "a" * 32, "a": old.replace("-", "")},
            )
        # end with
        assert client.put(f"/api/accounts/{old}", json={**BODY, "id": NEW_ID, "password": None}).status_code == 200
        with engine.begin() as connection:
            assert connection.execute(text("SELECT account_id FROM mail_events")).scalar_one() == NEW_ID.replace("-", "")
        # end with
    # end with
# end def


@pytest.fixture
def check_server() -> FakeServer:
    return FakeServer()
# end def


@pytest.fixture
def check_client(tmp_path: Path, check_server: FakeServer) -> Iterator[tuple[TestClient, list[ImapSettings]]]:
    seen: list[ImapSettings] = []

    def factory(imap_settings: ImapSettings) -> ImapConnection:
        seen.append(imap_settings)
        return check_server.connect(imap_settings)
    # end def

    with make_client(tmp_path, factory=factory) as test_client:
        yield test_client, seen
    # end with
# end def


def test_check_ok_does_not_touch_the_login_history(check_client: tuple[TestClient, list[ImapSettings]]) -> None:
    client, seen = check_client
    account = client.post("/api/accounts", json=BODY).json()
    response = client.post("/api/accounts/check", json={**BODY, "id": account["id"]})
    assert response.status_code == 200
    assert response.json() == {"ok": True, "kind": "ok", "message": "Login works."}
    assert [s.imap_username for s in seen] == ["me@work.example"]
    after = client.get(f"/api/accounts/{account['id']}").json()
    assert (after["auth_ok_at"], after["auth_failed_at"], after["auth_fail_count"]) == (None, None, 0)
# end def


def test_check_rejected_keeps_the_server_text_and_counts_nothing(check_client: tuple[TestClient, list[ImapSettings]], check_server: FakeServer) -> None:
    client, _ = check_client
    account = client.post("/api/accounts", json=BODY).json()
    check_server.login_answer = Response("NO", [b"authentication failed"])
    result = client.post("/api/accounts/check", json={**BODY, "id": account["id"]}).json()
    assert (result["ok"], result["kind"], result["message"]) == (False, "rejected", "authentication failed")
    after = client.get(f"/api/accounts/{account['id']}").json()
    assert (after["needs_check"], after["auth_fail_count"], after["auth_failed_at"]) == (False, 0, None)
# end def


def test_check_transient_refusal_is_unreachable(check_client: tuple[TestClient, list[ImapSettings]], check_server: FakeServer) -> None:
    client, _ = check_client
    check_server.login_answer = Response("NO", [b"[UNAVAILABLE] try later"])
    result = client.post("/api/accounts/check", json=BODY).json()
    assert (result["ok"], result["kind"]) == (False, "unreachable")
# end def


def test_check_without_password_uses_the_stored_one(check_client: tuple[TestClient, list[ImapSettings]]) -> None:
    client, seen = check_client
    account = client.post("/api/accounts", json=BODY).json()
    body = {key: value for key, value in BODY.items() if key != "password"}
    assert client.post("/api/accounts/check", json={**body, "id": account["id"], "host": "other.example"}).json()["ok"] is True
    assert (seen[-1].imap_password.get_secret_value(), seen[-1].imap_host) == ("secret", "other.example")
# end def


def test_check_without_password_and_account_is_422(check_client: tuple[TestClient, list[ImapSettings]]) -> None:
    client, _ = check_client
    body = {key: value for key, value in BODY.items() if key != "password"}
    assert client.post("/api/accounts/check", json=body).status_code == 422
# end def


@pytest.mark.parametrize(("error", "kind"), [(TimeoutError(), "timeout"), (OSError("down"), "unreachable")])
def test_check_failures_are_a_200(tmp_path: Path, error: Exception, kind: str) -> None:
    def broken(imap_settings: ImapSettings) -> ImapConnection:
        raise error
    # end def

    with make_client(tmp_path, factory=broken) as client:
        response = client.post("/api/accounts/check", json=BODY)
        assert (response.status_code, response.json()["kind"]) == (200, kind)
    # end with
# end def


def test_check_needs_the_login(tmp_path: Path) -> None:
    with make_client(tmp_path) as client:
        client.cookies.clear()
        assert client.post("/api/accounts/check", json=BODY).status_code == 401
    # end with
# end def
