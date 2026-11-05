"""The background watcher writes the action log."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import SecretStr

from remote_imap_mail_rules.db.accounts import create_account
from remote_imap_mail_rules.db.engine import create_engine, create_session_factory
from remote_imap_mail_rules.db.mail_events import list_events, record_event
from remote_imap_mail_rules.db.migrate import upgrade
from remote_imap_mail_rules.db.models import EventKind, MailEvent
from remote_imap_mail_rules.server.watcher import Watcher
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from remote_imap_mail_rules.config import ImapSettings

from .fake_imap import FakeConnection, FakeFolder, FakeServer
from .test_imap import ACCOUNT
from .test_server_accounts import KEY

RULES = f"""
rules:
  - name: invoices
    locations: [{{account_id: {ACCOUNT}}}]
    when: {{type: text, field: subject, operator: contains, value: invoice}}
"""


class StaticRules:
    source = "file"
    file_name = "rules.yml"

    def __init__(self, text: str | None) -> None:
        self.text = text
    # end def

    async def exists(self) -> bool:
        return self.text is not None
    # end def

    async def read_text(self) -> str | None:
        return self.text
    # end def

    async def save_text(self, text: str) -> None:
        self.text = text
    # end def
# end class


@pytest.fixture
async def factory(tmp_path: Path) -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    url = f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite3'}"
    await upgrade(url)
    engine = create_engine(url)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        await create_account(session, SecretStr(KEY), name="a", host="h", port=993, ssl=True, username="u", password="p", account_id=ACCOUNT)
        await session.commit()
    # end with
    yield session_factory
    await engine.dispose()
# end def


def make_watcher(factory: async_sessionmaker[AsyncSession], server: FakeServer, rules: str | None = RULES) -> Watcher:
    return Watcher(factory, StaticRules(rules), SecretStr(KEY), server.connect, retry_delay=0.05)
# end def


async def kinds(factory: async_sessionmaker[AsyncSession], folder: str, uid: int) -> list[tuple[str, str | None]]:
    async with factory() as session:
        return [(event.kind, event.rule_name) for event in await list_events(session, ACCOUNT, folder, uid)]
    # end with
# end def


async def until(check: Callable[[], Awaitable[bool]]) -> None:
    async with asyncio.timeout(3):
        while not await check():
            await asyncio.sleep(0.02)
        # end while
    # end async with
# end def


async def test_logs_first_seen_and_rule_matches(factory: async_sessionmaker[AsyncSession]) -> None:
    server = FakeServer()
    server.add("INBOX", 1, "invoice one")
    server.add("INBOX", 2, "hello")
    watcher = make_watcher(factory, server)
    watcher.start()
    try:
        await until(lambda: _has(factory, "INBOX", 1, [("first_seen", None), ("rule_match", "invoices")]))
        await until(lambda: _has(factory, "INBOX", 2, [("first_seen", None)]))
        async with factory() as session:
            [match] = (await session.scalars(select(MailEvent).where(MailEvent.kind == "rule_match"))).all()
        # end with
        assert match.detail == {"match_kind": "existing"}
        assert match.uidvalidity == 1
        assert match.message_id is None or match.message_id.startswith("<")

        await asyncio.sleep(0.1)  # let the folder task reach IDLE
        server.add("INBOX", 3, "another invoice")
        server.push()
        await until(lambda: _has(factory, "INBOX", 3, [("first_seen", None), ("rule_match", "invoices")]))
        await asyncio.sleep(0.2)
        # The new mail raised the mod-sequence too, which must not log it a second time as changed.
        assert await kinds(factory, "INBOX", 3) == [("first_seen", None), ("rule_match", "invoices")]
    finally:
        await watcher.stop()
    # end try
# end def


async def _has(factory: async_sessionmaker[AsyncSession], folder: str, uid: int, expected: list[tuple[str, str | None]]) -> bool:
    return await kinds(factory, folder, uid) == expected
# end def


async def test_last_run_is_set_when_the_watching_wakes_up(factory: async_sessionmaker[AsyncSession]) -> None:
    server = FakeServer()
    server.add("INBOX", 1, "invoice one")
    watcher = make_watcher(factory, server)
    assert watcher.last_run is None
    watcher.start()
    try:
        await until(lambda: _has(factory, "INBOX", 1, [("first_seen", None), ("rule_match", "invoices")]))
        await asyncio.sleep(0.1)  # let the folder task reach IDLE
        server.push()
        async with asyncio.timeout(3):
            while watcher.last_run is None:
                await asyncio.sleep(0.02)
            # end while
        # end async with
    finally:
        await watcher.stop()
    # end try
# end def


async def test_next_run_is_the_earliest_poll_still_ahead(factory: async_sessionmaker[AsyncSession]) -> None:
    watcher = make_watcher(factory, FakeServer())
    first, second = UUID(int=1), UUID(int=2)
    now = datetime.now(UTC)
    assert watcher.next_run() is None and not watcher.push_folders()
    watcher.scheduled(first, "INBOX", now + timedelta(seconds=60))
    watcher.scheduled(first, "Archive", now + timedelta(seconds=30))
    watcher.scheduled(second, "INBOX", now - timedelta(seconds=5))  # polling right now
    assert watcher.next_run() == now + timedelta(seconds=30)
    assert not watcher.push_folders()
    watcher.scheduled(second, "Sent", None)
    assert watcher.push_folders()
    await watcher.stop()
    assert watcher.next_run() is None and not watcher.push_folders()
# end def


async def test_a_polling_folder_gets_a_next_run_and_an_idle_one_does_not(factory: async_sessionmaker[AsyncSession]) -> None:
    polling = FakeServer(capabilities={"IMAP4REV1"})
    polling.add("INBOX", 1, "invoice one")
    watcher = make_watcher(factory, polling)
    watcher.start()
    try:
        async with asyncio.timeout(3):
            while watcher.next_run() is None:
                await asyncio.sleep(0.02)
            # end while
        # end async with
        assert not watcher.push_folders()
    finally:
        await watcher.stop()
    # end try
    idle = FakeServer()
    idle.add("INBOX", 1, "invoice one")
    watcher = make_watcher(factory, idle)
    watcher.start()
    try:
        async with asyncio.timeout(3):
            while not watcher.push_folders():
                await asyncio.sleep(0.02)
            # end while
        # end async with
        assert watcher.next_run() is None
    finally:
        await watcher.stop()
    # end try
# end def


async def test_restart_does_not_log_existing_mails_twice(factory: async_sessionmaker[AsyncSession]) -> None:
    server = FakeServer()
    server.add("INBOX", 1, "invoice one")
    watcher = make_watcher(factory, server)
    watcher.start()
    await until(lambda: _has(factory, "INBOX", 1, [("first_seen", None), ("rule_match", "invoices")]))
    await watcher.restart()
    await asyncio.sleep(0.3)
    await watcher.stop()
    assert await kinds(factory, "INBOX", 1) == [("first_seen", None), ("rule_match", "invoices")]
# end def


async def test_without_rules_or_when_disabled_nothing_happens(factory: async_sessionmaker[AsyncSession]) -> None:
    server = FakeServer()
    server.add("INBOX", 1, "invoice one")
    for watcher in (make_watcher(factory, server, None), make_watcher(factory, server, "rules: [")):
        watcher.start()
        await asyncio.sleep(0.2)
        await watcher.stop()
    # end for
    disabled = make_watcher(factory, server)
    disabled.enabled = False
    disabled.start()
    assert disabled.task is None
    assert await kinds(factory, "INBOX", 1) == []
# end def


async def test_connection_failures_are_retried(factory: async_sessionmaker[AsyncSession]) -> None:
    server = FakeServer()
    server.add("INBOX", 1, "invoice one")
    attempts: list[int] = []

    def flaky(settings: object):  # noqa: ANN202
        attempts.append(1)
        if len(attempts) == 1:
            raise OSError("no route to host")
        # end if
        return server.connect(settings)  # type: ignore[arg-type]
    # end def

    watcher = Watcher(factory, StaticRules(RULES), SecretStr(KEY), flaky, retry_delay=0.05)  # type: ignore[arg-type]
    watcher.start()
    try:
        await until(lambda: _has(factory, "INBOX", 1, [("first_seen", None), ("rule_match", "invoices")]))
    finally:
        await watcher.stop()
    # end try
    assert len(attempts) > 1
# end def


async def test_account_and_rule_edits_restart_the_watcher(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi.testclient import TestClient

    from remote_imap_mail_rules.server.app import create_app
    from remote_imap_mail_rules.server.auth import SESSION_COOKIE, make_session_token
    from remote_imap_mail_rules.server.settings import ServerSettings

    from .test_server_accounts import BODY

    restarts: list[int] = []

    async def restart(self: Watcher) -> None:
        restarts.append(1)
    # end def

    monkeypatch.setattr(Watcher, "restart", restart)
    settings = ServerSettings(
        _env_file=None, rules_path=None, database_url=f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite3'}",
        frontend_dist=tmp_path / "missing", secret_key=SecretStr(KEY), admin_username="admin", admin_password=SecretStr("admin-secret"),
    )
    with TestClient(create_app(settings)) as client:
        client.cookies.set(SESSION_COOKIE, make_session_token(settings))
        created = client.post("/api/accounts", json=BODY).json()
        assert len(restarts) == 1
        client.put(f"/api/accounts/{created['id']}", json=BODY)
        assert len(restarts) == 2
        assert client.put("/api/editor/rules", content=RULES.replace(str(ACCOUNT), created["id"])).status_code == 204
        assert len(restarts) == 3
        assert client.put("/api/editor/rules", content="rules: [").status_code == 422
        assert len(restarts) == 3
        assert client.delete(f"/api/accounts/{created['id']}").status_code == 409
        assert len(restarts) == 3
    # end with
# end def


ACTION_RULES = f"""
rules:
  - name: invoices
    locations: [{{account_id: {ACCOUNT}}}]
    when:
      type: all
      conditions:
        - {{type: text, field: subject, operator: contains, value: invoice}}
        - {{type: bool, field: seen, value: false}}
    actions:
      - {{type: mark_read}}
      - {{type: flag}}
  - name: archive
    locations: [{{account_id: {ACCOUNT}}}]
    when: {{type: text, field: subject, operator: contains, value: invoice}}
    actions:
      - {{type: move, folder: Archive}}
"""


def action_server() -> FakeServer:
    server = FakeServer({"IMAP4REV1", "IDLE", "CONDSTORE", "MOVE"})
    server.add("INBOX", 1, "invoice one")
    server.add("INBOX", 2, "hello")
    server.folders["Archive"] = FakeFolder()
    return server
# end def


def make_acting_watcher(factory: async_sessionmaker[AsyncSession], server: FakeServer, actions_enabled: bool) -> Watcher:
    return Watcher(factory, StaticRules(ACTION_RULES), SecretStr(KEY), server.connect, retry_delay=0.05, actions_enabled=actions_enabled)
# end def


async def action_events(factory: async_sessionmaker[AsyncSession]) -> list[tuple[str, str | None, dict[str, object]]]:
    async with factory() as session:
        events = (await session.scalars(select(MailEvent).where(MailEvent.kind == "action").order_by(MailEvent.created_at))).all()
        return [(event.detail["type"], event.rule_name, event.detail) for event in events]
    # end with
# end def


async def test_actions_are_applied_and_logged_when_enabled(factory: async_sessionmaker[AsyncSession]) -> None:
    server = action_server()
    watcher = make_acting_watcher(factory, server, actions_enabled=True)
    watcher.start()
    try:
        async def moved() -> bool:
            return [m.uid for m in server.folders["Archive"].messages] != [] and len(await action_events(factory)) >= 3
        # end def
        await until(moved)
        # `invoices` wins first and marks the mail read and flagged, which stops it matching, then `archive` moves it.
        events = await action_events(factory)
        assert [(kind, rule) for kind, rule, _ in events] == [("mark_read", "invoices"), ("flag", "invoices"), ("move", "archive")]
        assert all(detail["status"] == "done" for _, _, detail in events)
        assert events[2][2]["folder"] == "Archive"
        assert [m.uid for m in server.folders["INBOX"].messages] == [2]
        assert set(server.folders["Archive"].messages[0].flags.split()) == {"\\Seen", "\\Flagged"}
    finally:
        await watcher.stop()
    # end try
# end def


async def test_nothing_is_written_when_actions_are_disabled(factory: async_sessionmaker[AsyncSession]) -> None:
    server = action_server()
    watcher = make_acting_watcher(factory, server, actions_enabled=False)
    watcher.start()
    try:
        await until(lambda: _has(factory, "INBOX", 1, [("first_seen", None), ("rule_match", "invoices"), ("rule_match", "archive")]))
        await asyncio.sleep(0.2)
    finally:
        await watcher.stop()
    # end try
    assert await action_events(factory) == []
    assert not any(word in command for command in server.commands for word in ("STORE", "MOVE", "COPY", "EXPUNGE", "SELECT"))
    assert [m.uid for m in server.folders["INBOX"].messages] == [1, 2]
# end def


async def test_a_restart_does_not_repeat_actions(factory: async_sessionmaker[AsyncSession]) -> None:
    server = action_server()
    server.add("INBOX", 3, "invoice two", flags="\\Seen \\Flagged")
    server.folders["Archive"].messages.clear()
    watcher = make_acting_watcher(factory, server, actions_enabled=True)
    watcher.start()
    try:
        await until(lambda: _count(factory, 4))
        await asyncio.sleep(0.2)
        await watcher.restart()
        await asyncio.sleep(0.4)
    finally:
        await watcher.stop()
    # end try
    assert len(await action_events(factory)) == 4
    assert len(server.folders["Archive"].messages) == 2
# end def


async def _count(factory: async_sessionmaker[AsyncSession], expected: int) -> bool:
    return len(await action_events(factory)) >= expected
# end def


OTHER = UUID("0b8d3f4c-2b6e-4f0e-8f4a-3c8f6f1e9d22")

CROSS_RULES = f"""
rules:
  - name: ship
    locations: [{{account_id: {ACCOUNT}}}]
    when: {{type: text, field: subject, operator: contains, value: invoice}}
    actions:
      - {{type: move, folder: Inbox2, account_id: {OTHER}}}
"""


async def test_a_move_to_another_account_continues_the_log_under_the_new_key(factory: async_sessionmaker[AsyncSession]) -> None:
    async with factory() as session:
        await create_account(session, SecretStr(KEY), name="b", host="h2", port=993, ssl=True, username="u2", password="p2", account_id=OTHER)
        await session.commit()
    # end with
    source = FakeServer({"IMAP4REV1", "IDLE", "CONDSTORE", "UIDPLUS"})
    source.add("INBOX", 1, "invoice one", message_id="<m1@example.com>")
    target = FakeServer({"IMAP4REV1", "IDLE", "CONDSTORE", "UIDPLUS"})
    target.folders["Inbox2"] = FakeFolder(uidvalidity=9)
    target.add("Inbox2", 4, "old")

    def route(settings: ImapSettings) -> FakeConnection:
        return (source if settings.imap_account_id == ACCOUNT else target).connect(settings)
    # end def

    watcher = Watcher(factory, StaticRules(CROSS_RULES), SecretStr(KEY), route, retry_delay=0.05, actions_enabled=True)
    watcher.start()
    try:
        async def continued() -> bool:
            async with factory() as session:
                return bool(await list_events(session, OTHER, "Inbox2", 5))
            # end with
        # end def
        await until(continued)
        async with factory() as session:
            [old_key] = [e for e in await list_events(session, ACCOUNT, "INBOX", 1) if e.kind == "action"]
            [new_key] = await list_events(session, OTHER, "Inbox2", 5)
        # end with
        assert (old_key.detail["type"], old_key.detail["status"], old_key.detail["account_id"]) == ("move", "done", str(OTHER))
        assert (new_key.kind, new_key.rule_name, new_key.uidvalidity) == ("action", "ship", 9)
        assert new_key.detail == {"type": "moved_in", "status": "done", "from": {"account_id": str(ACCOUNT), "folder": "INBOX", "uid": 1}}
        assert old_key.message_id == new_key.message_id == "<m1@example.com>"
        assert source.folders["INBOX"].messages == []
        assert [m.uid for m in target.folders["Inbox2"].messages] == [4, 5]
    finally:
        await watcher.stop()
    # end try
# end def


async def test_a_mail_that_was_moved_too_often_is_not_moved_again(factory: async_sessionmaker[AsyncSession]) -> None:
    async with factory() as session:
        for number in range(5):
            await record_event(session, ACCOUNT, f"F{number}", 1, EventKind.action, message_id="<loop@example.com>", detail={"type": "move", "status": "done"})
        # end for
        await session.commit()
    # end with
    server = action_server()
    server.folders["INBOX"].messages[0].raw = b"From: a@example.com\r\nSubject: invoice one\r\nMessage-ID: <loop@example.com>\r\n\r\n"
    watcher = make_acting_watcher(factory, server, actions_enabled=True)
    watcher.start()
    try:
        async def refused() -> bool:
            return any(detail.get("reason") == "move_loop" for _, _, detail in await action_events(factory))
        # end def
        await until(refused)
    finally:
        await watcher.stop()
    # end try
    assert [m.uid for m in server.folders["INBOX"].messages] == [1, 2]
    assert server.folders["Archive"].messages == []
# end def


async def user_actions(factory: async_sessionmaker[AsyncSession]) -> list[tuple[str, int, dict[str, object]]]:
    async with factory() as session:
        events = (await session.scalars(select(MailEvent).where(MailEvent.kind == "user_action").order_by(MailEvent.created_at))).all()
        return [(event.folder, event.uid, event.detail) for event in events]
    # end with
# end def


async def test_changes_made_by_the_user_are_logged_but_the_first_load_is_not(factory: async_sessionmaker[AsyncSession]) -> None:
    server = FakeServer()
    server.add("INBOX", 1, "invoice one", message_id="<one@example.com>")
    server.add("INBOX", 2, "hello", flags="\\Flagged", message_id="<two@example.com>")
    watcher = make_watcher(factory, server)
    watcher.start()
    try:
        await until(lambda: _has(factory, "INBOX", 2, [("first_seen", None)]))
        await asyncio.sleep(0.1)
        assert await user_actions(factory) == []

        server.set_flags("INBOX", 2, "\\Seen")
        server.push()

        async def logged() -> bool:
            return len(await user_actions(factory)) == 1
        # end def
        await until(logged)
        assert await user_actions(factory) == [("INBOX", 2, {"type": "flags", "added": ["\\Seen"], "removed": ["\\Flagged"]})]

        server.delete("INBOX", 1)
        server.push()

        async def gone() -> bool:
            return len(await user_actions(factory)) == 2
        # end def
        await until(gone)
        assert (await user_actions(factory))[1] == ("INBOX", 1, {"type": "gone"})
        async with factory() as session:
            [event] = (await session.scalars(select(MailEvent).where(MailEvent.kind == "user_action", MailEvent.uid == 1))).all()
        # end with
        assert (event.message_id, event.uidvalidity) == ("<one@example.com>", 1)
    finally:
        await watcher.stop()
    # end try
# end def


async def test_changes_made_by_rule_actions_are_not_user_actions(factory: async_sessionmaker[AsyncSession]) -> None:
    server = action_server()
    watcher = make_acting_watcher(factory, server, actions_enabled=True)
    watcher.start()
    try:
        async def moved() -> bool:
            return [m.uid for m in server.folders["Archive"].messages] != [] and len(await action_events(factory)) >= 3
        # end def
        await until(moved)
        await asyncio.sleep(0.2)
        # The flags we set and the move away from INBOX both raised the mod-sequence, and neither is the user's doing.
        assert await user_actions(factory) == []
    finally:
        await watcher.stop()
    # end try
# end def
