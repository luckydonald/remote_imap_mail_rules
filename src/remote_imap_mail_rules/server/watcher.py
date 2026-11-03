"""Background watcher: runs the rules on every stored account and writes the action log (first seen, rule matches)."""

import asyncio
import contextlib
import logging
from dataclasses import dataclass
from uuid import UUID

import yaml
from aioimaplib import AioImapException
from pydantic import SecretStr, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..db import accounts as account_repository
from ..db import mail_events
from ..db.crypto import CryptoError
from ..db.models import EventKind
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


Entry = Seen | RuleMatch


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
    ) -> None:
        self.session_factory = session_factory
        self.rules_store = rules_store
        self.secret_key = secret_key
        self.imap_factory = imap_factory
        self.enabled = enabled
        self.retry_delay = retry_delay
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
        recorder = asyncio.create_task(self.record(queue))
        try:
            async for found in matches(settings, rule_file, self.imap_factory, on_inspect=lambda mail: queue.put_nowait(Seen(mail))):
                queue.put_nowait(found)
            # end for
            await queue.join()
        finally:
            recorder.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await recorder
            # end with
        # end try
    # end def

    async def record(self, queue: asyncio.Queue[Entry]) -> None:
        """Writes the entries in the order they were queued, so a mail's first seen precedes its matches."""
        while True:
            entry = await queue.get()
            try:
                async with self.session_factory() as session:
                    await self.write(session, entry)
                    await session.commit()
                # end with
            except Exception:
                logger.exception("Could not write the action log entry")
            finally:
                queue.task_done()
            # end try
        # end while
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

    async def add(self, session: AsyncSession, mail: Mail, kind: EventKind, *, rule_name: str | None = None, detail: dict[str, str] | None = None) -> None:
        await mail_events.record_event(
            session,
            mail.account_id,
            mail.folder,
            mail.uid,
            kind,
            uidvalidity=mail.uidvalidity,
            message_id=str(mail.headers.get("Message-ID")) if mail.headers.get("Message-ID") else None,
            rule_name=rule_name,
            detail=detail,
        )
    # end def
# end class
