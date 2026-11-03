"""The background watcher writes the action log."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import pytest
from pydantic import SecretStr

from remote_imap_mail_rules.db.accounts import create_account
from remote_imap_mail_rules.db.engine import create_engine, create_session_factory
from remote_imap_mail_rules.db.mail_events import list_events
from remote_imap_mail_rules.db.migrate import upgrade
from remote_imap_mail_rules.db.models import MailEvent
from remote_imap_mail_rules.server.watcher import Watcher
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .fake_imap import FakeFolder, FakeServer
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
        frontend_dist=tmp_path / "missing", secret_key=SecretStr(KEY),
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
