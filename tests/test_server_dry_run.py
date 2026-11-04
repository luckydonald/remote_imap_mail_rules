"""The dry run and "Run now" API, against the FakeServer."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from remote_imap_mail_rules.server.app import create_app
from remote_imap_mail_rules.server.auth import SESSION_COOKIE, make_session_token
from remote_imap_mail_rules.server.settings import ServerSettings

from .fake_imap import FakeFolder, FakeServer
from .test_server_accounts import BODY, KEY


def rules_text(account: str) -> str:
    return f"""
rules:
  - name: invoices
    locations: [{{account_id: {account}}}]
    when:
      type: all
      conditions:
        - {{type: text, field: subject, operator: contains, value: invoice}}
        - {{type: bool, field: seen, value: false}}
    actions:
      - {{type: mark_read}}
      - {{type: move, folder: Archive}}
  - name: everything
    locations: [{{account_id: {account}}}]
    when: {{type: text, field: subject, operator: contains, value: hello}}
    actions:
      - {{type: flag}}
"""
# end def


def make_server() -> FakeServer:
    server = FakeServer({"IMAP4REV1", "MOVE", "CONDSTORE"})
    server.add("INBOX", 1, "invoice one")
    server.add("INBOX", 2, "invoice two", flags="\\Seen")
    server.add("INBOX", 3, "hello")
    server.folders["Archive"] = FakeFolder()
    return server
# end def


def run_client(tmp_path: Path, server: FakeServer, actions_enabled: bool) -> Iterator[TestClient]:
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


def test_dry_run_summarizes_and_lists_without_writing(client: TestClient, server: FakeServer, account: str) -> None:
    commands = len(server.commands)
    response = client.post("/api/dry-run", json={"rule": "invoices"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert (data["inspected"], data["affected"], data["next"], data["actions_enabled"]) == (3, 1, None, False)
    assert {(row["type"], row["status"], row["folder"], row["count"]) for row in data["summary"]} == {("mark_read", "planned", None, 1), ("move", "planned", "Archive", 1)}
    [mail] = data["mails"]
    assert (mail["uid"], mail["folder"], mail["moved_to"]) == (1, "INBOX", "Archive")
    assert [round_["rule"] for round_ in mail["rounds"]] == ["invoices"]
    assert not any(word in command for command in server.commands[commands:] for word in ("STORE", "MOVE", "COPY", "EXPUNGE", "SELECT"))
    assert [m.uid for m in server.folders["INBOX"].messages] == [1, 2, 3]
# end def


def test_dry_run_of_the_unsaved_file(client: TestClient, account: str) -> None:
    text = rules_text(account).replace("value: invoice}", "value: nothing}")
    data = client.post("/api/dry-run", json={"rule": "invoices", "yaml": text}).json()
    assert data["affected"] == 0 and data["summary"] == []
    assert client.post("/api/dry-run", json={"rule": "invoices", "yaml": "rules: ["}).status_code == 422
    assert client.post("/api/dry-run", json={"rule": "missing"}).status_code == 404
# end def


def test_dry_run_needs_the_login(client: TestClient) -> None:
    client.cookies.clear()
    assert client.post("/api/dry-run", json={"rule": "invoices"}).status_code == 401
# end def


def test_config_tells_whether_actions_are_enabled(client: TestClient) -> None:
    assert client.get("/api/editor/config").json()["actions_enabled"] is False
# end def


def test_run_now_is_refused_while_actions_are_disabled(client: TestClient, server: FakeServer, account: str) -> None:
    response = client.post("/api/dry-run/run", json={"rule": "invoices"})
    assert (response.status_code, response.json()["detail"]) == (409, "actions_disabled")
    assert [m.uid for m in server.folders["INBOX"].messages] == [1, 2, 3]
# end def


def test_run_now_applies_and_logs(tmp_path: Path) -> None:
    server = make_server()
    for client in run_client(tmp_path, server, actions_enabled=True):
        account_id = client.post("/api/accounts", json=BODY).json()["id"]
        client.put("/api/editor/rules", content=rules_text(account_id))
        assert client.get("/api/editor/config").json()["actions_enabled"] is True
        data = client.post("/api/dry-run/run", json={"rule": "invoices"}).json()
        assert (data["applied"], data["errors"], data["steps"]) == (1, [], {"done": 2})
        assert [m.uid for m in server.folders["INBOX"].messages] == [2, 3]
        assert set(server.folders["Archive"].messages[0].flags.split()) == {"\\Seen"}
        events = client.get(f"/api/mail/accounts/{account_id}/messages/1/events", params={"folder": "INBOX"}).json()
        assert [(event["kind"], event["rule_name"], event["detail"]["type"]) for event in events] == [
            ("action", "invoices", "mark_read"), ("action", "invoices", "move"),
        ]
    # end for
# end def


def test_dry_run_comes_in_pages(client: TestClient, server: FakeServer, account: str) -> None:
    pages = []
    cursor = None
    while True:
        data = client.post("/api/dry-run", json={"rule": "invoices", "limit": 1, "cursor": cursor}).json()
        pages.append(data)
        cursor = data["next"]
        if cursor is None:
            break
        # end if
    # end while
    # Newest first: uid 3 (hello), uid 2 (seen invoice, nothing to do), uid 1 (the one that is affected).
    assert [(page["inspected"], page["affected"]) for page in pages] == [(1, 0), (1, 0), (1, 1)]
    assert [mail["uid"] for page in pages for mail in page["mails"]] == [1]
    assert pages[-1]["summary"][0]["count"] == 1
# end def


def test_a_page_may_end_exactly_at_the_end(client: TestClient, account: str) -> None:
    data = client.post("/api/dry-run", json={"rule": "invoices", "limit": 3}).json()
    assert (data["inspected"], data["affected"]) == (3, 1)
    # Nothing known to be left, but the folder is only known to be done by asking again.
    if data["next"] is not None:
        again = client.post("/api/dry-run", json={"rule": "invoices", "limit": 3, "cursor": data["next"]}).json()
        assert (again["inspected"], again["next"]) == (0, None)
    # end if
# end def
