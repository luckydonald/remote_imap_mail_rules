"""The core generator: yields the mails that match the rules, first the existing ones, then new and changed ones as they arrive."""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from enum import StrEnum
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


class MatchKind(StrEnum):
    existing = "existing"
    new = "new"
    changed = "changed"
# end class


@dataclass(frozen=True)
class RuleMatch:
    rule: Rule
    mail: Mail
    kind: MatchKind
# end class


async def rules_by_folder(client: ImapClient, rule_file: RuleFile, account_id: UUID) -> dict[str, list[Rule]]:
    """Which enabled rules apply to which folder of this account; `recursive` locations are expanded via `LIST`."""
    result: dict[str, list[Rule]] = {}
    for rule in rule_file.rules:
        if not rule.enabled:
            continue
        # end if
        for location in rule.locations:
            if location.account_id != account_id:
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


async def match_mails(rules: list[Rule], mails: list[Mail], kind: MatchKind, on_inspect: InspectCallback | None = None) -> list[RuleMatch]:
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
    client: ImapClient, settings: ImapSettings, folder: str, rules: list[Rule], queue: "asyncio.Queue[Queued]", on_inspect: InspectCallback | None = None
) -> int:
    """Puts the matches of all mails currently in the folder on the queue. Returns the highest UID seen."""
    highest_uid = 0
    async for page in client.iter_pages(settings.imap_account_id, folder, settings.imap_page_size):
        highest_uid = max([highest_uid, *(mail.uid for mail in page)])
        for item in await match_mails(rules, page, MatchKind.existing, on_inspect):
            await queue.put(item)
        # end for
    # end async for
    return highest_uid
# end def


async def follow_changes(
    client: ImapClient, settings: ImapSettings, folder: str, rules: list[Rule], queue: "asyncio.Queue[Queued]", highest_uid: int,
    on_inspect: InspectCallback | None = None,
) -> None:
    """Watches the folder and puts matches of new and changed mails on the queue."""
    state = client.state
    assert state is not None
    validity, modseq = state.uidvalidity, state.highestmodseq
    async for _event in watch(client, folder, settings.imap_poll_interval):
        current = await client.poll_state(folder)
        if current.uidvalidity != validity:
            logger.warning("UIDVALIDITY of %s changed, reloading the folder", folder)
            validity, modseq = current.uidvalidity, current.highestmodseq
            highest_uid = await load_existing(client, settings, folder, rules, queue, on_inspect)
            continue
        # end if
        if current.uidnext > highest_uid + 1:
            await client.examine(folder)
            fresh = await client.fetch_new(settings.imap_account_id, folder, highest_uid)
            highest_uid = max([highest_uid, *(mail.uid for mail in fresh)])
            for item in await match_mails(rules, fresh, MatchKind.new, on_inspect):
                await queue.put(item)
            # end for
        # end if
        if modseq is not None and current.highestmodseq is not None and current.highestmodseq > modseq:
            await client.examine(folder)
            changed = await client.fetch_changed(settings.imap_account_id, folder, modseq)
            for item in await match_mails(rules, [mail for mail in changed if mail.uid <= highest_uid], MatchKind.changed, on_inspect):
                await queue.put(item)
            # end for
            modseq = current.highestmodseq
        # end if
    # end async for
# end def


async def follow_folder(
    settings: ImapSettings,
    factory: ConnectionFactory,
    folder: str,
    rules: list[Rule],
    queue: "asyncio.Queue[Queued]",
    follow: bool,
    on_inspect: InspectCallback | None = None,
) -> None:
    """Loads the folder page by page, then watches it. Puts the failure on the queue instead of raising it."""
    try:
        async with ImapClient(settings, factory) as client:
            highest_uid = await load_existing(client, settings, folder, rules, queue, on_inspect)
            if follow:
                await follow_changes(client, settings, folder, rules, queue, highest_uid, on_inspect)
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
    settings: ImapSettings, rule_file: RuleFile, factory: ConnectionFactory = connect_aioimaplib, follow: bool = True,
    on_inspect: InspectCallback | None = None,
) -> AsyncIterator[RuleMatch]:
    """Yields every mail matching a rule: existing mails first (newest first per folder), then new and changed ones as they arrive.

    Each folder gets its own connection and task, because `IDLE` blocks the connection it runs on.
    With `follow=False` only the existing mails are yielded and the generator ends.
    `on_inspect` is called for every mail that gets evaluated, whether or not a rule matches it.
    """
    async with ImapClient(settings, factory) as client:
        folders = await rules_by_folder(client, rule_file, settings.imap_account_id)
    # end with
    queue: asyncio.Queue[Queued] = asyncio.Queue()
    tasks = [asyncio.create_task(follow_folder(settings, factory, folder, rules, queue, follow, on_inspect)) for folder, rules in folders.items()]
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
