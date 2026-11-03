"""The action log repository."""

from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from remote_imap_mail_rules.db.accounts import create_account
from remote_imap_mail_rules.db.engine import create_engine, create_session_factory
from remote_imap_mail_rules.db.mail_events import has_event, list_events, record_event
from remote_imap_mail_rules.db.migrate import upgrade
from remote_imap_mail_rules.db.models import EventKind

from .test_server_accounts import KEY


@pytest.fixture
async def session(tmp_path: Path) -> AsyncIterator[AsyncSession]:
    url = f"sqlite+aiosqlite:///{tmp_path / 'db.sqlite3'}"
    await upgrade(url)
    engine = create_engine(url)
    async with create_session_factory(engine)() as db:
        yield db
    # end with
    await engine.dispose()
# end def


async def make_account(session: AsyncSession):  # noqa: ANN201
    return await create_account(
        session, SecretStr(KEY), name="a", host="h", port=993, ssl=True, username="u", password="p"
    )
# end def


async def test_record_and_list_oldest_first(session: AsyncSession) -> None:
    account = await make_account(session)
    await record_event(session, account.id, "INBOX", 1, EventKind.first_seen, uidvalidity=7)
    await record_event(
        session, account.id, "INBOX", 1, EventKind.rule_match, rule_name="r", detail={"match_kind": "new"}
    )
    await record_event(session, account.id, "INBOX", 2, EventKind.first_seen)
    await record_event(session, account.id, "Other", 1, EventKind.first_seen)
    events = await list_events(session, account.id, "INBOX", 1)
    assert [event.kind for event in events] == ["first_seen", "rule_match"]
    assert events[1].detail == {"match_kind": "new"}
# end def


async def test_has_event_distinguishes_rule_and_uidvalidity(session: AsyncSession) -> None:
    account = await make_account(session)
    await record_event(session, account.id, "INBOX", 1, EventKind.rule_match, uidvalidity=7, rule_name="r")
    args = (session, account.id, "INBOX", 1, EventKind.rule_match)
    assert await has_event(*args, uidvalidity=7, rule_name="r")
    assert not await has_event(*args, uidvalidity=7, rule_name="other")
    assert not await has_event(*args, uidvalidity=8, rule_name="r")
    assert not await has_event(*args, uidvalidity=7)
    assert not await has_event(session, uuid4(), "INBOX", 1, EventKind.rule_match, uidvalidity=7, rule_name="r")
# end def


async def test_events_vanish_with_their_account(session: AsyncSession) -> None:
    account = await make_account(session)
    await record_event(session, account.id, "INBOX", 1, EventKind.first_seen)
    await session.commit()
    await session.delete(account)
    await session.commit()
    assert await list_events(session, account.id, "INBOX", 1) == []
# end def
