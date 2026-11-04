"""The accounts API and the seeding from the environment."""

import logging
from collections.abc import Iterator
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text

from remote_imap_mail_rules.server.app import create_app
from remote_imap_mail_rules.server.auth import SESSION_COOKIE, make_session_token
from remote_imap_mail_rules.server.settings import ServerSettings
from tests.conftest import ACCOUNT_ID
from tests.settings import TestImapSettings

KEY = Fernet.generate_key().decode()
BODY = {"name": "Work", "host": "imap.work.example", "port": 993, "ssl": True, "username": "me@work.example", "password": "secret"}


def make_client(tmp_path: Path, key: str | None = KEY, env: TestImapSettings | None = None) -> TestClient:
    settings = ServerSettings(
        _env_file=None,
        rules_path=tmp_path / "rules.yml",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite3'}",
        frontend_dist=tmp_path / "missing",
        secret_key=SecretStr(key) if key else None, admin_username="admin", admin_password=SecretStr("admin-secret"),
    )
    client = TestClient(create_app(settings, env))
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
