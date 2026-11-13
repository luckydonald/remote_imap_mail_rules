"""The stats API: `/api/stats`."""

from pathlib import Path

from fastapi.testclient import TestClient

from remote_imap_mail_rules.server.api.stats import sqlite_size

from .test_server_accounts import BODY
from .test_server_events import client, insert  # noqa: F401 - `client` is a fixture


def test_needs_the_login(client: TestClient) -> None:  # noqa: F811
    client.cookies.clear()
    assert client.get("/api/stats").status_code == 401
# end def


def test_counts_follow_the_rows(client: TestClient, tmp_path: Path) -> None:  # noqa: F811
    account_id: str = client.post("/api/accounts", json=BODY).json()["id"]
    insert(tmp_path, account_id, "INBOX", 1, "first_seen", "2026-11-03 10:00:00.000000")
    insert(tmp_path, account_id, "INBOX", 1, "rule_match", "2026-11-03 10:00:05.000000", "invoices")
    insert(tmp_path, account_id, "INBOX", 2, "rule_match", "2026-11-03 10:00:09.000000", "invoices")
    stats = client.get("/api/stats").json()
    assert stats["tables"]["accounts"] == 1
    assert stats["tables"]["mail_events"] == 3
    assert stats["tables"]["mail_events_by_kind"] == {"first_seen": 1, "rule_match": 2}
    assert stats["first_event"].startswith("2026-11-03T10:00:00")
    assert stats["last_event"].startswith("2026-11-03T10:00:09")
    assert stats["database"]["dialect"] == "sqlite"
    assert stats["database"]["size_bytes"] > 0
    assert stats["watcher"]["jobs"] == 0
    assert stats["started_at"]
# end def


def test_does_not_leak_paths(client: TestClient, tmp_path: Path) -> None:  # noqa: F811
    assert str(tmp_path) not in client.get("/api/stats").text
# end def


def test_sqlite_size_only_for_a_file(tmp_path: Path) -> None:
    file = tmp_path / "db.sqlite3"
    file.write_bytes(b"x" * 10)
    (tmp_path / "db.sqlite3-wal").write_bytes(b"y" * 5)
    assert sqlite_size(f"sqlite+aiosqlite:///{file}") == 15
    assert sqlite_size("sqlite+aiosqlite:///:memory:") is None
    assert sqlite_size("postgresql+asyncpg://user@host/db") is None
# end def
