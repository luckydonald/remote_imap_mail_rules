"""The account, folder, event and dry-run tools, and the redaction of mail titles, against the FakeServer and a database store."""

import json
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from .fake_imap import FakeServer
from .mcp_helpers import call, new_token, text_of
from .test_server_accounts import BODY
from .test_server_dry_run import make_server, rules_text, run_client


@pytest.fixture
def server() -> FakeServer:
    return make_server()
# end def


@pytest.fixture
def client(tmp_path: Path, server: FakeServer) -> Iterator[TestClient]:
    yield from run_client(tmp_path, server, actions_enabled=False)
# end def


@pytest.fixture
def account(client: TestClient) -> str:
    account_id: str = client.post("/api/accounts", json=BODY).json()["id"]
    assert client.put("/api/editor/rules", content=rules_text(account_id)).status_code == 204
    return account_id
# end def


def insert_event(tmp_path: Path, account_id: str, uid: int, kind: str, created: str, detail: dict[str, object], message_id: str | None = None) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'db.sqlite3'}")
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO mail_events (id, account_id, folder, uid, message_id, kind, rule_name, detail, created_at)"
                " VALUES (:id, :account, 'INBOX', :uid, :message_id, :kind, 'invoices', :detail, :created)"
            ),
            {"id": uuid4().hex, "account": account_id.replace("-", ""), "uid": uid, "message_id": message_id, "kind": kind,
             "detail": json.dumps(detail), "created": created},
        )
    # end with
    engine.dispose()
# end def


def test_accounts_read_without_password(client: TestClient, account: str) -> None:
    token = new_token(client, ["accounts:r"])
    listed = call(client, token, "list_accounts")["structuredContent"]["accounts"]
    assert [a["id"] for a in listed] == [account] and listed[0]["has_password"] is True
    assert "secret" not in json.dumps(listed)
    assert call(client, token, "get_account", {"account_id": account})["structuredContent"]["name"] == "Work"
    assert call(client, token, "get_account", {"account_id": str(uuid4())})["isError"] is True
# end def


def test_password_scopes_are_separate(client: TestClient, account: str) -> None:
    read = new_token(client, ["accounts:r", "accounts:w", "accounts:d"])
    assert call(client, read, "get_account_password", {"account_id": account})["isError"] is True
    values = {"name": "Renamed"}
    assert call(client, read, "update_account", {"account_id": account, "values": values})["structuredContent"]["name"] == "Renamed"
    refused = call(client, read, "update_account", {"account_id": account, "values": {"password": "new"}})
    assert refused["isError"] is True and "accounts.password:w" in text_of(refused)
    assert call(client, read, "create_account", {"name": "x", "host": "h", "username": "u", "password": "p"})["isError"] is True  # needs the scope

    password = new_token(client, ["accounts.password:r", "accounts.password:w"])
    assert call(client, password, "get_account_password", {"account_id": account})["structuredContent"] == {"password": "secret"}
    assert call(client, password, "set_account_password", {"account_id": account, "password": "other"})["isError"] is False
    assert call(client, password, "get_account_password", {"account_id": account})["structuredContent"] == {"password": "other"}
    assert client.get(f"/api/accounts/{account}").json()["name"] == "Renamed"  # the other fields stayed
# end def


def test_create_and_delete_account(client: TestClient) -> None:
    token = new_token(client, ["accounts:r", "accounts:w", "accounts:d", "accounts.password:w"])
    created = call(client, token, "create_account", {"name": "New", "host": "imap.example", "username": "u", "password": "pw"})
    new_id = created["structuredContent"]["id"]
    assert [a["id"] for a in client.get("/api/accounts").json()] == [new_id]
    assert call(client, token, "delete_account", {"account_id": new_id})["isError"] is False
    assert client.get("/api/accounts").json() == []
# end def


def test_delete_account_is_refused_while_a_rule_uses_it(client: TestClient, account: str) -> None:
    token = new_token(client, ["accounts:d"])
    result = call(client, token, "delete_account", {"account_id": account})
    assert result["isError"] is True and "invoices" in text_of(result)
# end def


def test_list_folders(client: TestClient, account: str) -> None:
    token = new_token(client, ["folders:r"])
    folders = call(client, token, "list_folders", {"account_id": account})["structuredContent"]["folders"]
    assert {"INBOX", "Archive"} <= {folder["name"] for folder in folders}
# end def


def test_events_list_filter_and_clear(client: TestClient, tmp_path: Path, account: str) -> None:
    insert_event(tmp_path, account, 1, "first_seen", "2026-11-03 10:00:00.000000", {"type": "x"})
    insert_event(tmp_path, account, 2, "rule_match", "2026-11-03 10:00:05.000000", {"type": "y"})
    token = new_token(client, ["events:r", "events:d"])
    page = call(client, token, "list_events", {"limit": 1})["structuredContent"]
    assert [item["uid"] for item in page["items"]] == [2] and page["next"]
    following = call(client, token, "list_events", {"limit": 1, "before": page["next"]})["structuredContent"]
    assert [item["uid"] for item in following["items"]] == [1] and following["next"] is None
    assert [i["uid"] for i in call(client, token, "list_events", {"kinds": ["first_seen"]})["structuredContent"]["items"]] == [1]
    assert call(client, token, "list_events", {"kinds": ["nope"]})["isError"] is True
    assert call(client, token, "clear_events", {"kinds": ["first_seen"]})["structuredContent"] == {"deleted": 1}
    assert call(client, token, "clear_events")["structuredContent"] == {"deleted": 1}
    assert call(client, token, "list_events")["structuredContent"]["items"] == []
# end def


def test_events_hide_mail_titles_without_mails_r(client: TestClient, tmp_path: Path, account: str) -> None:
    detail = {"type": "flags", "subject": "Secret invoice", "from": "Max <max@example.com>"}
    insert_event(tmp_path, account, 1, "user_action", "2026-11-03 10:00:00.000000", detail, "<abc@example.com>")
    hidden = call(client, new_token(client, ["events:r"]), "list_events")["structuredContent"]["items"][0]
    assert "Secret" not in json.dumps(hidden) and "max@example.com" not in json.dumps(hidden) and "abc@example.com" not in json.dumps(hidden)
    assert hidden["detail"]["type"] == "flags"
    shown = call(client, new_token(client, ["events:r", "mails:r"]), "list_events")["structuredContent"]["items"][0]
    assert shown["detail"] == detail and shown["message_id"] == "<abc@example.com>"
# end def


def test_dry_run_masks_titles_without_mails_r(client: TestClient, server: FakeServer, account: str) -> None:
    commands = len(server.commands)
    hidden = call(client, new_token(client, ["rules:r"]), "dry_run", {"rule": "invoices"})["structuredContent"]
    assert hidden["affected"] == 1 and "invoice one" not in json.dumps(hidden)
    shown = call(client, new_token(client, ["rules:r", "mails:r"]), "dry_run", {"rule": "invoices"})["structuredContent"]
    assert shown["mails"][0]["subject"] == "invoice one"
    assert not any(word in command for command in server.commands[commands:] for word in ("STORE", "MOVE", "COPY", "EXPUNGE"))
    assert call(client, new_token(client, ["rules:r"]), "dry_run", {"rule": "missing"})["isError"] is True
# end def


def test_edits_in_database_mode(client: TestClient, account: str) -> None:
    token = new_token(client, ["rules:r", "rules:w", "rules:d"])
    assert call(client, token, "add_action", {"rule": "everything", "action": {"type": "mark_read"}})["isError"] is False
    assert call(client, token, "move_rule", {"name": "everything", "index": 0})["structuredContent"] == {"index": 0}
    assert [r["name"] for r in call(client, token, "list_rules")["structuredContent"]["rules"]] == ["everything", "invoices"]
    assert call(client, token, "save_template", {"name": "t", "template": {"content": {"type": "bool", "field": "seen"}}})["isError"] is False
    assert call(client, token, "list_templates")["structuredContent"] == {"templates": ["t"]}
    assert call(client, token, "add_condition", {"rule": "invoices", "path": [], "condition": {"type": "template", "ref": "t"}})["isError"] is False
    refused = call(client, token, "delete_template", {"name": "t"})
    assert refused["isError"] is True and "invoices" in text_of(refused)
# end def
