"""The action log API."""

from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, text

from remote_imap_mail_rules.server.app import create_app
from remote_imap_mail_rules.server.auth import SESSION_COOKIE, make_session_token
from remote_imap_mail_rules.server.settings import ServerSettings

from .test_server_accounts import BODY, KEY


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    settings = ServerSettings(
        _env_file=None, rules_path=None, database_url=f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite3'}",
        frontend_dist=tmp_path / "missing", secret_key=SecretStr(KEY),
    )
    with TestClient(create_app(settings)) as test_client:
        test_client.cookies.set(SESSION_COOKIE, make_session_token(settings))
        yield test_client
    # end with
# end def


def insert(tmp_path: Path, account_id: str, folder: str, uid: int, kind: str, created: str, rule: str | None = None) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite3'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO mail_events (id, account_id, folder, uid, kind, rule_name, detail, created_at)"
                " VALUES (:id, :account, :folder, :uid, :kind, :rule, :detail, :created)"
            ),
            {"id": uuid4().hex, "account": account_id.replace("-", ""), "folder": folder, "uid": uid,
             "kind": kind, "rule": rule, "detail": '{"match_kind": "new"}', "created": created},
        )
    # end with
    engine.dispose()
# end def


def test_lists_the_log_of_one_mail_oldest_first(client: TestClient, tmp_path: Path) -> None:
    account_id = client.post("/api/accounts", json=BODY).json()["id"]
    insert(tmp_path, account_id, "INBOX", 1, "rule_match", "2026-11-03 10:00:05", "invoices")
    insert(tmp_path, account_id, "INBOX", 1, "first_seen", "2026-11-03 10:00:00")
    insert(tmp_path, account_id, "INBOX", 2, "first_seen", "2026-11-03 10:00:00")
    response = client.get(f"/api/mail/accounts/{account_id}/messages/1/events", params={"folder": "INBOX"})
    assert response.status_code == 200
    events = response.json()
    assert [(event["kind"], event["rule_name"]) for event in events] == [("first_seen", None), ("rule_match", "invoices")]
    assert events[1]["detail"] == {"match_kind": "new"}
    assert events[0]["created_at"].startswith("2026-11-03T10:00:00")
# end def


def test_empty_for_a_mail_without_log(client: TestClient) -> None:
    account_id = client.post("/api/accounts", json=BODY).json()["id"]
    assert client.get(f"/api/mail/accounts/{account_id}/messages/9/events", params={"folder": "INBOX"}).json() == []
# end def
