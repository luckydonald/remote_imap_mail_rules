"""Background watcher: runs the rules on every stored account and writes the action log (first seen, rule matches, and the actions if enabled)."""

import asyncio
import contextlib
import logging
from collections.abc import Coroutine
from dataclasses import dataclass
from datetime import UTC, datetime
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
from ..db.models import Account, EventKind, MailEvent
from ..actions import MAX_MOVES, ActionRunner, ChainResult, StepStatus
from ..imap.client import ConnectionFactory, ImapError
from ..mail import Mail
from ..matching import Change, FlagChange, MailGone, MatchKind, RuleMatch, matches
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


@dataclass(frozen=True)
class UserChange:
    """A change on the server that our own actions did not make, so the user (or another client) did."""

    change: Change
# end class


@dataclass(frozen=True)
class Job:
    """Something the watcher is busy with right now: a folder being checked, or the rules being run over one mail."""

    kind: str
    """`folder` or `actions`."""
    account_id: UUID
    folder: str
    uid: int | None
    started_at: datetime
# end class


Entry = Seen | RuleMatch | Act | UserChange

IGNORED_FLAGS = frozenset({"\\Recent"})
"""Set by the server, never by anybody on purpose."""

Key = tuple[str, int]
"""`(folder, uid)` of a mail within the account a `follow()` is for."""

LOGGED_STATUSES = {StepStatus.done, StepStatus.error, StepStatus.skipped}
"""A `noop` step changed nothing, so it is not worth a log entry (and a rerun after a restart stays silent)."""


def message_id_of(mail: Mail) -> str | None:
    value = mail.headers.get("Message-ID")
    return str(value) if value else None
# end def


class OwnChanges:
    """Which flag changes and disappearances of mails came from our own actions, to keep them out of the `user_action` log.

    The decision is taken when the change is noticed, not when it is written: while a mail's rules run, everything on it is ours.
    Afterwards the flags the chain ended with, and a move, are remembered once, so the change noticed late is still recognised.
    """

    def __init__(self) -> None:
        self.acting: set[Key] = set()
        self.flags: dict[Key, frozenset[str]] = {}
        self.moved: set[Key] = set()
    # end def

    def finished(self, key: Key, before: frozenset[str], result: ChainResult) -> None:
        if result.moved is not None:
            self.moved.add(key)
        elif frozenset(result.mail.flags) != before:
            self.flags[key] = frozenset(result.mail.flags)
        # end if
    # end def

    def is_own(self, change: Change) -> bool:
        if isinstance(change, MailGone):
            key = (change.folder, change.uid)
            return key in self.acting or key in self.moved
        # end if
        key = (change.mail.folder, change.mail.uid)
        if key in self.acting:
            return True
        # end if
        expected = self.flags.pop(key, None)
        return expected is not None and expected == frozenset(change.mail.flags)
    # end def

    def report(self, change: Change, queue: "asyncio.Queue[Entry]") -> None:
        if not self.is_own(change):
            queue.put_nowait(UserChange(change))
        # end if
    # end def
# end class


async def uncancellable[T](coro: Coroutine[Any, Any, T]) -> T:
    """Runs the coroutine to its end even if the caller is cancelled meanwhile, then lets the cancellation through.

    A task cancelled in the middle of a database write makes SQLAlchemy log "Exception during reset or similar" (a Sentry event),
    because the connection is rolled back while it is being cancelled. The writes are short, so waiting for them is cheap.
    """
    task = asyncio.ensure_future(coro)
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        if not task.done():
            await asyncio.wait({task})
        # end if
        raise
    # end try
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
        self.last_run: datetime | None = None
        self.due: dict[tuple[UUID, str], datetime | None] = {}
        self.jobs: dict[tuple[Any, ...], Job] = {}
    # end def

    def start(self) -> None:
        if self.enabled and self.task is None:
            self.task = asyncio.create_task(self.run())
        # end if
    # end def

    async def stop(self) -> None:
        task, self.task = self.task, None
        self.due.clear()
        self.jobs.clear()
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
        account = await uncancellable(self.load_account(account_id))
        if account is None:
            return None
        # end if
        try:
            return account_repository.imap_settings(account, self.secret_key)
        except CryptoError:
            return None
        # end try
    # end def

    async def load_account(self, account_id: UUID) -> Account | None:
        async with self.session_factory() as session:
            return await account_repository.get_account(session, account_id)
        # end with
    # end def

    async def load_events(self, message_id: str) -> list[MailEvent]:
        async with self.session_factory() as session:
            return await mail_events.list_events_by_message_id(session, message_id, EventKind.action)
        # end with
    # end def

    async def allow_move(self, mail: Mail) -> bool:
        """Refuses a mail that rules already moved `MAX_MOVES` times, found by its `Message-ID` across all folders and accounts."""
        message_id = message_id_of(mail)
        if message_id is None:
            return True
        # end if
        events = await uncancellable(self.load_events(message_id))
        moves = [event for event in events if event.detail.get("type") == "move" and event.detail.get("status") == "done"]
        return len(moves) < MAX_MOVES
    # end def

    def ticked(self) -> None:
        """The watching of some folder woke up (a push or a poll). Kept in memory only, so it is `None` after a restart."""
        self.last_run = datetime.now(UTC)
    # end def

    def scheduled(self, account_id: UUID, folder: str, due: datetime | None) -> None:
        """A folder says when its next poll is due, or `None` while it waits for a server push (`IDLE`). It is idle again, so its job ends."""
        self.due[(account_id, folder)] = due
        self.jobs.pop(("folder", account_id, folder), None)
    # end def

    def working(self, account_id: UUID, folder: str) -> None:
        """The folder is being looked at; the job ends with the next `scheduled()` of that folder."""
        self.jobs.setdefault(("folder", account_id, folder), Job("folder", account_id, folder, None, datetime.now(UTC)))
    # end def

    def working_jobs(self) -> list[Job]:
        """What the watcher is busy with right now, oldest first."""
        return sorted(self.jobs.values(), key=lambda job: job.started_at)
    # end def

    def next_run(self) -> datetime | None:
        """The earliest poll still ahead. A due time in the past is a poll that is running right now, so it does not count."""
        now = datetime.now(UTC)
        ahead = [due for due in self.due.values() if due is not None and due > now]
        return min(ahead, default=None)
    # end def

    def push_folders(self) -> bool:
        """Whether some folder waits for a server push instead of polling."""
        return any(due is None for due in self.due.values())
    # end def

    def inspected(self, account_id: UUID, mail: Mail, queue: "asyncio.Queue[Entry]") -> None:
        self.working(account_id, mail.folder)
        queue.put_nowait(Seen(mail))
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
        own = OwnChanges()
        runner = ActionRunner(settings, rule_file, self.imap_factory, self.lookup_settings, self.allow_move) if self.actions_enabled else None
        recorder = asyncio.create_task(self.record(queue, runner, pending, own))
        try:
            async for found in matches(
                settings, rule_file, self.imap_factory, on_inspect=lambda mail: self.inspected(account_id, mail, queue),
                on_change=lambda change: own.report(change, queue), on_poll=self.ticked,
                on_schedule=lambda folder, due: self.scheduled(account_id, folder, due),
            ):
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

    async def record(
        self, queue: asyncio.Queue[Entry], runner: ActionRunner | None = None, pending: set[tuple[str, int, int | None]] | None = None,
        own: "OwnChanges | None" = None,
    ) -> None:
        """Writes the entries in the order they were queued, so a mail's first seen precedes its matches."""
        while True:
            entry = await queue.get()
            try:
                result = None
                if isinstance(entry, Act):
                    if pending is not None:
                        pending.discard((entry.mail.folder, entry.mail.uid, entry.mail.uidvalidity))
                    # end if
                    if runner is not None:
                        # IMAP work, a restart may abort it.
                        result = await self.run_actions(runner, entry.mail, own)
                    # end if
                # end if
                await uncancellable(self.commit_entry(entry, runner is not None, result))
            except Exception:
                logger.exception("Could not write the action log entry")
            finally:
                queue.task_done()
            # end try
        # end while
    # end def

    async def commit_entry(self, entry: Entry, acting: bool, result: ChainResult | None) -> None:
        """The database part of one entry, one session. Kept away from cancellation by `uncancellable`, see there."""
        async with self.session_factory() as session:
            if isinstance(entry, Act):
                if acting:
                    await self.write_actions(session, result)
                # end if
            else:
                await self.write(session, entry)
            # end if
            await session.commit()
        # end with
    # end def

    async def run_actions(self, runner: ActionRunner, mail: Mail, own: "OwnChanges | None") -> ChainResult | None:
        """Runs the rules over the mail and tells `own` what that changed, so the watching does not take it for the user's doing."""
        job_key = ("actions", mail.account_id, mail.folder, mail.uid)
        self.jobs[job_key] = Job("actions", mail.account_id, mail.folder, mail.uid, datetime.now(UTC))
        try:
            if own is None:
                return await runner.run(mail)
            # end if
            key, before = (mail.folder, mail.uid), frozenset(mail.flags)
            own.acting.add(key)
            try:
                result = await runner.run(mail)
            finally:
                own.acting.discard(key)
            # end try
            if result is not None:
                own.finished(key, before, result)
            # end if
            return result
        finally:
            self.jobs.pop(job_key, None)
        # end try
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
        if isinstance(entry, UserChange):
            await self.write_user_change(session, entry.change)
            return
        # end if
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

    async def write_user_change(self, session: AsyncSession, change: Change) -> None:
        if isinstance(change, FlagChange):
            now = frozenset(change.mail.flags) - IGNORED_FLAGS
            before = change.old_flags - IGNORED_FLAGS
            detail: dict[str, Any] = {"type": "flags", "added": sorted(now - before), "removed": sorted(before - now)}
            if not detail["added"] and not detail["removed"]:
                return
            # end if
            await self.add(session, change.mail, EventKind.user_action, detail=detail)
            return
        # end if
        await mail_events.record_event(
            session, change.account_id, change.folder, change.uid, EventKind.user_action,
            uidvalidity=change.uidvalidity, message_id=change.message_id, detail={"type": "gone"},
        )
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
