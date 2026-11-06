"""The action log across all mails: `/api/log`."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient

from remote_imap_mail_rules.server.watcher import Job

from .test_server_accounts import BODY
from .test_server_events import client, insert  # noqa: F401 - `client` is a fixture


def setup(client: TestClient, tmp_path: Path) -> str:  # noqa: F811
    account_id: str = client.post("/api/accounts", json=BODY).json()["id"]
    insert(tmp_path, account_id, "INBOX", 1, "first_seen", "2026-11-03 10:00:00.000000")
    insert(tmp_path, account_id, "INBOX", 1, "rule_match", "2026-11-03 10:00:05.000000", "invoices")
    insert(tmp_path, account_id, "Archive", 2, "action", "2026-11-03 10:00:10.000000", "invoices")
    insert(tmp_path, account_id, "INBOX", 3, "user_action", "2026-11-03 10:00:20.000000")
    return account_id
# end def


def test_lists_newest_first_with_the_mail_key(client: TestClient, tmp_path: Path) -> None:  # noqa: F811
    account_id = setup(client, tmp_path)
    response = client.get("/api/log/events")
    assert response.status_code == 200
    page = response.json()
    assert [(entry["kind"], entry["folder"], entry["uid"]) for entry in page["items"]] == [
        ("user_action", "INBOX", 3), ("action", "Archive", 2), ("rule_match", "INBOX", 1), ("first_seen", "INBOX", 1),
    ]
    assert page["items"][0]["account_id"] == account_id
    assert page["items"][0]["created_at"].endswith("Z")
    assert page["next"] is None
# end def


def test_filters(client: TestClient, tmp_path: Path) -> None:  # noqa: F811
    account_id = setup(client, tmp_path)

    def uids(**params: object) -> list[int]:
        return [entry["uid"] for entry in client.get("/api/log/events", params=params).json()["items"]]
    # end def

    assert uids(folder="Archive") == [2]
    assert uids(kind=["first_seen", "action"]) == [2, 1]
    assert uids(rule="invoices") == [2, 1]
    assert uids(since="2026-11-03T10:00:06Z") == [3, 2]
    assert uids(until="2026-11-03T10:00:05Z") == [1, 1]
    assert uids(account_id=account_id, folder="INBOX", kind=["rule_match"]) == [1]
    assert uids(account_id="00000000-0000-0000-0000-000000000000") == []
# end def


def test_search_ignores_case_and_looks_into_the_detail(client: TestClient, tmp_path: Path) -> None:  # noqa: F811
    setup(client, tmp_path)

    def uids(text: str) -> list[int]:
        return [entry["uid"] for entry in client.get("/api/log/events", params={"q": text}).json()["items"]]
    # end def

    assert uids("INVOICES") == [2, 1]
    assert uids("archive") == [2]
    assert uids("match_kind") == [3, 2, 1, 1]
    assert uids("100%") == []
# end def


def test_pages_with_a_cursor(client: TestClient, tmp_path: Path) -> None:  # noqa: F811
    setup(client, tmp_path)
    first = client.get("/api/log/events", params={"limit": 3}).json()
    assert [entry["uid"] for entry in first["items"]] == [3, 2, 1]
    assert first["next"] is not None
    second = client.get("/api/log/events", params={"limit": 3, "before": first["next"]}).json()
    assert [(entry["kind"]) for entry in second["items"]] == ["first_seen"]
    assert second["next"] is None
# end def


def test_pages_through_entries_of_the_same_second(client: TestClient, tmp_path: Path) -> None:  # noqa: F811
    account_id = client.post("/api/accounts", json=BODY).json()["id"]
    for uid in range(1, 6):
        insert(tmp_path, account_id, "INBOX", uid, "first_seen", "2026-11-03 10:00:00.000000")
    # end for
    seen: list[int] = []
    cursor: str | None = None
    while True:
        params: dict[str, object] = {"limit": 2}
        if cursor is not None:
            params["before"] = cursor
        # end if
        page = client.get("/api/log/events", params=params).json()
        seen += [entry["uid"] for entry in page["items"]]
        cursor = page["next"]
        if cursor is None:
            break
        # end if
    # end while
    assert sorted(seen) == [1, 2, 3, 4, 5]
# end def


def test_rejects_a_broken_cursor(client: TestClient) -> None:  # noqa: F811
    assert client.get("/api/log/events", params={"before": "nonsense"}).status_code == 422
# end def


def test_status(client: TestClient, tmp_path: Path) -> None:  # noqa: F811
    empty = client.get("/api/log/status").json()
    assert empty == {"watcher_enabled": False, "last_run": None, "next_run": None, "push": False, "last_change": None, "last_action": None, "jobs": []}
    setup(client, tmp_path)
    status = client.get("/api/log/status").json()
    assert status["last_change"].startswith("2026-11-03T10:00:20")
    assert status["last_action"].startswith("2026-11-03T10:00:10")
# end def


def test_status_lists_the_working_jobs(client: TestClient) -> None:  # noqa: F811
    watcher = client.app.state.watcher  # type: ignore[attr-defined]
    account = UUID(int=1)
    watcher.jobs[("folder", account, "INBOX")] = Job("folder", account, "INBOX", None, datetime(2026, 11, 3, 10, tzinfo=UTC))
    watcher.jobs[("actions", account, "INBOX", 4)] = Job("actions", account, "INBOX", 4, datetime(2026, 11, 3, 11, tzinfo=UTC))
    jobs = client.get("/api/log/status").json()["jobs"]
    assert [(job["kind"], job["account_id"], job["folder"], job["uid"]) for job in jobs] == [
        ("folder", str(account), "INBOX", None), ("actions", str(account), "INBOX", 4),
    ]
    assert jobs[0]["started_at"].startswith("2026-11-03T10:00:00")
# end def


def test_log_needs_login(client: TestClient) -> None:  # noqa: F811
    client.cookies.clear()
    assert client.get("/api/log/events").status_code == 401
    assert client.get("/api/log/status").status_code == 401
# end def
