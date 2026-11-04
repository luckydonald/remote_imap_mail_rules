"""Background watcher: runs the rules on every stored account and writes the action log (first seen, rule matches, and the actions if enabled)."""

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import yaml
from aioimaplib import AioImapException
from pydantic import SecretStr, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..config import ImapSettings
from ..db import accounts as account_repository
from ..db import mail_events
from ..db.crypto import CryptoError
from ..db.models import EventKind
from ..actions import MAX_MOVES, ActionRunner, ChainResult, StepStatus
from ..imap.client import ConnectionFactory, ImapError
from ..mail import Mail
from ..matching import MatchKind, RuleMatch, matches
from ..rules.loader import parse_rules
from .rules_store import RulesStore

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Seen:
    mail: Mail
# end class


@dataclass(frozen=True)
class Act:
    """Run the rules for real over this mail (queued once per mail after its first match)."""

    mail: Mail
# end class


Entry = Seen | RuleMatch | Act

LOGGED_STATUSES = {StepStatus.done, StepStatus.error, StepStatus.skipped}
"""A `noop` step changed nothing, so it is not worth a log entry (and a rerun after a restart stays silent)."""


def message_id_of(mail: Mail) -> str | None:
    value = mail.headers.get("Message-ID")
    return str(value) if value else None
# end def


class Watcher:
    """One task per stored account. `restart()` re-reads the accounts and the rules, e.g. after either was edited."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        rules_store: RulesStore,
        secret_key: SecretStr | None,
        imap_factory: ConnectionFactory,
        *,
        enabled: bool = True,
        retry_delay: float = 30.0,
        actions_enabled: bool = False,
    ) -> None:
        self.session_factory = session_factory
        self.rules_store = rules_store
        self.secret_key = secret_key
        self.imap_factory = imap_factory
        self.enabled = enabled
        self.retry_delay = retry_delay
        self.actions_enabled = actions_enabled
        self.task: asyncio.Task[None] | None = None
    # end def

    def start(self) -> None:
        if self.enabled and self.task is None:
            self.task = asyncio.create_task(self.run())
        # end if
    # end def

    async def stop(self) -> None:
        task, self.task = self.task, None
        if task is None:
            return
        # end if
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        # end with
    # end def

    async def restart(self) -> None:
        await self.stop()
        self.start()
    # end def

    async def run(self) -> None:
        async with self.session_factory() as session:
            account_ids = [account.id for account in await account_repository.list_accounts(session)]
        # end with
        await asyncio.gather(*(self.watch_account(account_id) for account_id in account_ids))
    # end def

    async def watch_account(self, account_id: UUID) -> None:
        """Follows the account; a connection failure is retried after `retry_delay`, a bad setup waits for the next `restart()`."""
        while True:
            try:
                await self.follow(account_id)
                return
            except asyncio.CancelledError:
                raise
            except (ImapError, AioImapException, OSError, TimeoutError) as error:
                logger.warning("Watching account %s failed, retrying in %.0f s: %s", account_id, self.retry_delay, error)
            except Exception:
                logger.exception("Watching account %s crashed, retrying in %.0f s", account_id, self.retry_delay)
            # end try
            await asyncio.sleep(self.retry_delay)
        # end while
    # end def

    async def lookup_settings(self, account_id: UUID) -> ImapSettings | None:
        """The connection settings of a stored account, `None` if it does not exist or its password cannot be decrypted."""
        async with self.session_factory() as session:
            account = await account_repository.get_account(session, account_id)
        # end with
        if account is None:
            return None
        # end if
        try:
            return account_repository.imap_settings(account, self.secret_key)
        except CryptoError:
            return None
        # end try
    # end def

    async def allow_move(self, mail: Mail) -> bool:
        """Refuses a mail that rules already moved `MAX_MOVES` times, found by its `Message-ID` across all folders and accounts."""
        message_id = message_id_of(mail)
        if message_id is None:
            return True
        # end if
        async with self.session_factory() as session:
            events = await mail_events.list_events_by_message_id(session, message_id, EventKind.action)
        # end with
        moves = [event for event in events if event.detail.get("type") == "move" and event.detail.get("status") == "done"]
        return len(moves) < MAX_MOVES
    # end def

    async def follow(self, account_id: UUID) -> None:
        async with self.session_factory() as session:
            account = await account_repository.get_account(session, account_id)
        # end with
        if account is None:
            return
        # end if
        try:
            settings = account_repository.imap_settings(account, self.secret_key)
        except CryptoError as error:
            logger.warning("Not watching account %s: %s", account_id, error)
            return
        # end try
        text = await self.rules_store.read_text()
        if text is None:
            logger.info("Not watching account %s: there are no rules yet", account_id)
            return
        # end if
        try:
            rule_file = parse_rules(text)
        except (yaml.YAMLError, ValidationError) as error:
            logger.warning("Not watching account %s: the rules are invalid: %s", account_id, error)
            return
        # end try
        queue: asyncio.Queue[Entry] = asyncio.Queue()
        pending: set[tuple[str, int, int | None]] = set()
        runner = ActionRunner(settings, rule_file, self.imap_factory, self.lookup_settings, self.allow_move) if self.actions_enabled else None
        recorder = asyncio.create_task(self.record(queue, runner, pending))
        try:
            async for found in matches(settings, rule_file, self.imap_factory, on_inspect=lambda mail: queue.put_nowait(Seen(mail))):
                queue.put_nowait(found)
                key = (found.mail.folder, found.mail.uid, found.mail.uidvalidity)
                if runner is not None and key not in pending:
                    pending.add(key)
                    queue.put_nowait(Act(found.mail))
                # end if
            # end for
            await queue.join()
        finally:
            recorder.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await recorder
            # end with
            if runner is not None:
                await runner.close()
            # end if
        # end try
    # end def

    async def record(self, queue: asyncio.Queue[Entry], runner: ActionRunner | None = None, pending: set[tuple[str, int, int | None]] | None = None) -> None:
        """Writes the entries in the order they were queued, so a mail's first seen precedes its matches."""
        while True:
            entry = await queue.get()
            try:
                async with self.session_factory() as session:
                    if isinstance(entry, Act):
                        if pending is not None:
                            pending.discard((entry.mail.folder, entry.mail.uid, entry.mail.uidvalidity))
                        # end if
                        if runner is not None:
                            await self.write_actions(session, await runner.run(entry.mail))
                        # end if
                    else:
                        await self.write(session, entry)
                    # end if
                    await session.commit()
                # end with
            except Exception:
                logger.exception("Could not write the action log entry")
            finally:
                queue.task_done()
            # end try
        # end while
    # end def

    async def write_actions(self, session: AsyncSession, result: ChainResult | None) -> None:
        """One `action` entry per step that did something, under the key the mail had when the step ran."""
        if result is None:
            return
        # end if
        for round_ in result.rounds:
            for step in round_.steps:
                if step.status in LOGGED_STATUSES:
                    detail: dict[str, Any] = {"type": step.type, "status": step.status.value, **step.args}
                    if step.reason:
                        detail["reason"] = step.reason
                    # end if
                    await self.add(session, result.mail, EventKind.action, rule_name=round_.rule.name, detail=detail)
                # end if
            # end for
        # end for
        if result.moved is not None and result.moved.uid is not None and result.rounds:
            await self.continue_log(session, result)
        # end if
    # end def

    async def continue_log(self, session: AsyncSession, result: ChainResult) -> None:
        """Starts the log of a moved mail under its new key, linked to the old one by `message_id` and `from`.

        The target folder's watcher still writes its own `first_seen` there, once it sees the mail.
        """
        moved, mail = result.moved, result.mail
        assert moved is not None and moved.uid is not None
        await mail_events.record_event(
            session,
            moved.account_id,
            moved.folder,
            moved.uid,
            EventKind.action,
            uidvalidity=moved.uidvalidity,
            message_id=message_id_of(mail),
            rule_name=result.rounds[-1].rule.name,
            detail={"type": "moved_in", "status": "done", "from": {"account_id": str(mail.account_id), "folder": mail.folder, "uid": mail.uid}},
        )
    # end def

    async def write(self, session: AsyncSession, entry: Entry) -> None:
        if isinstance(entry, Seen):
            mail = entry.mail
            if not await mail_events.has_event(session, mail.account_id, mail.folder, mail.uid, EventKind.first_seen, uidvalidity=mail.uidvalidity):
                await self.add(session, mail, EventKind.first_seen)
            # end if
            return
        # end if
        mail, name = entry.mail, entry.rule.name
        # Existing mails are matched again on every start, so those are logged once; new and changed ones every time.
        if entry.kind is MatchKind.existing and await mail_events.has_event(
            session, mail.account_id, mail.folder, mail.uid, EventKind.rule_match, uidvalidity=mail.uidvalidity, rule_name=name
        ):
            return
        # end if
        await self.add(session, mail, EventKind.rule_match, rule_name=name, detail={"match_kind": entry.kind.value})
    # end def

    async def add(self, session: AsyncSession, mail: Mail, kind: EventKind, *, rule_name: str | None = None, detail: dict[str, Any] | None = None) -> None:
        await mail_events.record_event(
            session,
            mail.account_id,
            mail.folder,
            mail.uid,
            kind,
            uidvalidity=mail.uidvalidity,
            message_id=message_id_of(mail),
            rule_name=rule_name,
            detail=detail,
        )
    # end def
# end class
