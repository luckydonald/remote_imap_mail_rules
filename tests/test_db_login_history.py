"""The login history on an account."""

from collections.abc import AsyncIterator
from datetime import timedelta
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from remote_imap_mail_rules.db.accounts import create_account, record_login, update_account
from remote_imap_mail_rules.db.engine import create_engine, create_session_factory
from remote_imap_mail_rules.db.migrate import upgrade
from remote_imap_mail_rules.db.models import Account

from .test_server_accounts import KEY

SECRET = SecretStr(KEY)


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


async def make_account(session: AsyncSession) -> Account:
    return await create_account(session, SECRET, name="a", host="h", port=993, ssl=True, username="u", password="p")
# end def


async def update(session: AsyncSession, account: Account, **changes: object) -> None:
    values: dict[str, object] = dict(name="a", host="h", port=993, ssl=True, username="u", password=None, page_size=50, poll_interval=60.0)
    values.update(changes)
    await update_account(session, SECRET, account, **values)  # type: ignore[arg-type]
# end def


async def test_failure_flags_and_success_clears_but_keeps_the_history(session: AsyncSession) -> None:
    account = await make_account(session)
    assert not account.needs_check
    await record_login(session, account.id, "authentication failed")
    await record_login(session, account.id, "authentication failed")
    assert (account.needs_check, account.auth_fail_count, account.auth_last_error) == (True, 2, "authentication failed")
    await record_login(session, account.id, None)
    assert (account.needs_check, account.auth_fail_count) == (False, 2)
    assert account.auth_failed_at is not None and account.auth_ok_at is not None
# end def


async def test_successes_are_written_at_most_every_five_minutes(session: AsyncSession) -> None:
    account = await make_account(session)
    await record_login(session, account.id, None)
    first = account.auth_ok_at
    assert first is not None
    await record_login(session, account.id, None)
    assert account.auth_ok_at == first
    account.auth_ok_at = first - timedelta(minutes=6)
    await record_login(session, account.id, None)
    assert account.auth_ok_at > first - timedelta(minutes=1)
# end def


async def test_new_credentials_reset_the_history_but_other_changes_do_not(session: AsyncSession) -> None:
    account = await make_account(session)
    await record_login(session, account.id, "authentication failed")
    created = account.auth_updated_at
    await update(session, account, host="other", name="b")
    assert (account.needs_check, account.auth_fail_count, account.auth_updated_at) == (True, 1, created)
    await update(session, account, password="new")
    assert (account.needs_check, account.auth_fail_count, account.auth_last_error, account.auth_ok_at) == (False, 0, None, None)
    assert account.auth_updated_at > created
    await record_login(session, account.id, "authentication failed")
    await update(session, account, username="other")
    assert (account.needs_check, account.auth_fail_count) == (False, 0)
# end def
