"""The core generator: yields the mails that match the rules, first the existing ones, then new and changed ones as they arrive."""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Never
from uuid import UUID

from .config import ImapSettings
from .imap.client import ConnectionFactory, ImapClient, connect_aioimaplib
from .imap.watcher import watch
from .mail import Mail
from .rules.evaluate import evaluate
from .rules.models import Rule, RuleFile

logger = logging.getLogger(__name__)

InspectCallback = Callable[[Mail], None]
"""Called once for every mail a rule evaluation looks at, matching or not."""


@dataclass(frozen=True)
class FlagChange:
    """The flags of a mail already known to us changed on the server."""

    mail: Mail
    old_flags: frozenset[str]
# end class


@dataclass(frozen=True)
class MailGone:
    """A mail we knew is no longer in the folder (deleted, expunged or moved away)."""

    account_id: UUID
    folder: str
    uidvalidity: int | None
    uid: int
    message_id: str | None
# end class


Change = FlagChange | MailGone

ChangeCallback = Callable[[Change], None]
"""Called for every flag change and every vanished mail the watching sees, whether or not a rule matches the mail.

The first load of a folder is the baseline and reports nothing.
"""


PollCallback = Callable[[], None]
ScheduleCallback = Callable[[str, datetime | None], None]
"""Called every time the watching of a folder wakes up (a push or a poll), whether or not anything changed."""


@dataclass
class Known:
    """What we remember of a mail to notice later changes."""

    flags: frozenset[str]
    message_id: str | None
    uidvalidity: int | None
# end class


KnownMails = dict[int, Known]
"""The mails of one folder by UID."""


def remember(known: KnownMails, mails: list[Mail]) -> None:
    for mail in mails:
        value = mail.headers.get("Message-ID")
        known[mail.uid] = Known(flags=frozenset(mail.flags), message_id=str(value) if value else None, uidvalidity=mail.uidvalidity)
    # end for
# end def


class MatchKind(StrEnum):
    existing = "existing"
    new = "new"
    changed = "changed"
# end class


@dataclass(frozen=True)
class RuleMatch:
    rule: Rule[Never]
    mail: Mail
    kind: MatchKind
# end class


async def rules_by_folder(client: ImapClient, rule_file: RuleFile[Never], account_id: UUID) -> dict[str, list[Rule[Never]]]:
    """Which enabled rules apply to which folder of this account; `recursive` locations are expanded via `LIST`."""
    result: dict[str, list[Rule[Never]]] = {}
    for rule in rule_file.rules:
        if not rule.enabled:
            continue
        # end if
        for location in rule.locations:
            if location.account_id != account_id:
                logger.debug("Rule %r: skipping location of account %s, this is account %s", rule.name, location.account_id, account_id)
                continue
            # end if
            for folder in await client.expand_folder(location.folder, location.recursive):
                rules = result.setdefault(folder, [])
                if rule not in rules:
                    rules.append(rule)
                # end if
            # end for
        # end for
    # end for
    return result
# end def


async def match_mails(rules: list[Rule[Never]], mails: list[Mail], kind: MatchKind, on_inspect: InspectCallback | None = None) -> list[RuleMatch]:
    found: list[RuleMatch] = []
    for mail in mails:
        if on_inspect is not None:
            on_inspect(mail)
        # end if
        for rule in rules:
            if await evaluate(rule.when, mail):
                found.append(RuleMatch(rule=rule, mail=mail, kind=kind))
            # end if
        # end for
    # end for
    return found
# end def


class Finished:
    """Put on the queue when a folder task ends without failure."""
# end class


Queued = RuleMatch | BaseException | Finished


async def load_existing(
    client: ImapClient, settings: ImapSettings, folder: str, rules: list[Rule[Never]], queue: "asyncio.Queue[Queued]", on_inspect: InspectCallback | None = None,
    known: KnownMails | None = None,
) -> int:
    """Puts the matches of all mails currently in the folder on the queue. Returns the highest UID seen."""
    highest_uid = 0
    if known is not None:
        known.clear()
    # end if
    async for page in client.iter_pages(settings.imap_account_id, folder, settings.imap_page_size):
        highest_uid = max([highest_uid, *(mail.uid for mail in page)])
        if known is not None:
            remember(known, page)
        # end if
        for item in await match_mails(rules, page, MatchKind.existing, on_inspect):
            await queue.put(item)
        # end for
    # end async for
    return highest_uid
# end def


async def follow_changes(
    client: ImapClient, settings: ImapSettings, folder: str, rules: list[Rule[Never]], queue: "asyncio.Queue[Queued]", highest_uid: int,
    on_inspect: InspectCallback | None = None, on_change: ChangeCallback | None = None, known: KnownMails | None = None,
    on_poll: PollCallback | None = None, on_schedule: ScheduleCallback | None = None,
) -> None:
    """Watches the folder and puts matches of new and changed mails on the queue.

    With `on_change`, flag changes and vanished mails are reported too; `known` is the snapshot `load_existing` filled.
    `on_poll` is called on every wake-up, before the folder is looked at.
    `on_schedule` gets the folder and when its next poll is due (`None` while it waits in `IDLE`).
    """
    if known is None:
        known = {}
    # end if
    state = client.state
    assert state is not None
    validity, modseq = state.uidvalidity, state.highestmodseq
    async for _event in watch(client, folder, settings.imap_poll_interval, on_schedule=None if on_schedule is None else lambda due: on_schedule(folder, due)):
        if on_poll is not None:
            on_poll()
        # end if
        current = await client.poll_state(folder)
        if current.uidvalidity != validity:
            logger.warning("UIDVALIDITY of %s changed, reloading the folder", folder)
            validity, modseq = current.uidvalidity, current.highestmodseq
            highest_uid = await load_existing(client, settings, folder, rules, queue, on_inspect, known)
            continue
        # end if
        known_uid = highest_uid
        if current.uidnext > highest_uid + 1:
            await client.examine(folder)
            fresh = await client.fetch_new(settings.imap_account_id, folder, highest_uid)
            highest_uid = max([highest_uid, *(mail.uid for mail in fresh)])
            remember(known, fresh)
            for item in await match_mails(rules, fresh, MatchKind.new, on_inspect):
                await queue.put(item)
            # end for
        # end if
        if modseq is not None and current.highestmodseq is not None and current.highestmodseq > modseq:
            await client.examine(folder)
            changed = await client.fetch_changed(settings.imap_account_id, folder, modseq)
            if on_change is not None:
                for mail in changed:
                    before = known.get(mail.uid)
                    if before is not None and before.flags != frozenset(mail.flags):
                        on_change(FlagChange(mail=mail, old_flags=before.flags))
                        before.flags = frozenset(mail.flags)
                    # end if
                # end for
            # end if
            for item in await match_mails(rules, [mail for mail in changed if mail.uid <= known_uid], MatchKind.changed, on_inspect):
                await queue.put(item)
            # end for
        # Without CONDSTORE nothing tells us a mail was expunged, so every poll has to look.
        if on_change is not None and (modseq is None or current.highestmodseq is None or current.highestmodseq > modseq):
            present = set(await client.list_uids(folder))
            for uid in sorted(set(known) - present):
                gone = known.pop(uid)
                on_change(MailGone(account_id=settings.imap_account_id, folder=folder, uidvalidity=gone.uidvalidity, uid=uid, message_id=gone.message_id))
            # end for
        # end if
        modseq = current.highestmodseq if current.highestmodseq is not None else modseq
    # end async for
# end def


async def follow_folder(
    settings: ImapSettings,
    factory: ConnectionFactory,
    folder: str,
    rules: list[Rule[Never]],
    queue: "asyncio.Queue[Queued]",
    follow: bool,
    on_inspect: InspectCallback | None = None,
    on_change: ChangeCallback | None = None,
    on_poll: PollCallback | None = None,
    on_schedule: ScheduleCallback | None = None,
) -> None:
    """Loads the folder page by page, then watches it. Puts the failure on the queue instead of raising it."""
    try:
        async with ImapClient(settings, factory) as client:
            known: KnownMails = {}
            highest_uid = await load_existing(client, settings, folder, rules, queue, on_inspect, known)
            if follow:
                await follow_changes(client, settings, folder, rules, queue, highest_uid, on_inspect, on_change, known, on_poll, on_schedule)
            # end if
        # end async with
        await queue.put(Finished())
    except asyncio.CancelledError:
        raise
    except Exception as error:  # noqa: BLE001 - handed to the consumer, which re-raises it
        await queue.put(error)
    # end try
# end def


async def matches(
    settings: ImapSettings, rule_file: RuleFile[Never], factory: ConnectionFactory = connect_aioimaplib, follow: bool = True,
    on_inspect: InspectCallback | None = None, on_change: ChangeCallback | None = None, on_poll: PollCallback | None = None,
    on_schedule: ScheduleCallback | None = None,
) -> AsyncIterator[RuleMatch]:
    """Yields every mail matching a rule: existing mails first (newest first per folder), then new and changed ones as they arrive.

    Each folder gets its own connection and task, because `IDLE` blocks the connection it runs on.
    With `follow=False` only the existing mails are yielded and the generator ends.
    `on_inspect` is called for every mail that gets evaluated, whether or not a rule matches it.
    `on_change` is called with a `FlagChange` or `MailGone` for every change the watching notices after the first load, matching or not.
    `on_poll` is called whenever the watching of any folder wakes up, so a caller can tell the watching is alive.
    `on_schedule` is called with a folder and its next poll time, or `None` when that folder waits for a server push.
    """
    async with ImapClient(settings, factory) as client:
        folders = await rules_by_folder(client, rule_file, settings.imap_account_id)
    # end with
    if not folders:
        logger.warning(
            "No folder to watch: none of the enabled rules has a location for account %s (IMAP_ACCOUNT_ID); rules refer to %s",
            settings.imap_account_id,
            sorted({str(location.account_id) for rule in rule_file.rules if rule.enabled for location in rule.locations}),
        )
    # end if
    for folder, folder_rules in folders.items():
        logger.debug("Queued folder %s with rules %s", folder, [rule.name for rule in folder_rules])
    # end for
    logger.debug("Inspecting %d folders: %s", len(folders), list(folders))
    queue: asyncio.Queue[Queued] = asyncio.Queue()
    tasks = [asyncio.create_task(follow_folder(settings, factory, folder, rules, queue, follow, on_inspect, on_change, on_poll, on_schedule)) for folder, rules in folders.items()]
    running = len(tasks)
    try:
        while running:
            item = await queue.get()
            if isinstance(item, BaseException):
                raise item
            # end if
            if isinstance(item, Finished):
                running -= 1
                continue
            # end if
            yield item
        # end while
    finally:
        for task in tasks:
            task.cancel()
        # end for
        await asyncio.gather(*tasks, return_exceptions=True)
    # end try
# end def
