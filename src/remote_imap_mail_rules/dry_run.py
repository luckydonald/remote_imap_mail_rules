"""Dry run of one rule: what its actions would do to the mails it covers, without writing anything.

The first matching rule wins and changes feed back into the evaluation, so one rule cannot be looked at alone.
Every mail in the rule's folders runs through the whole chain of `actions.run_chain` with a `VirtualWriter`, and the mails whose chain
involves the chosen rule are kept, each with the complete chain, so the user also sees when an earlier rule shadows theirs.
"""

import logging
from collections import Counter
from dataclasses import dataclass, field, replace
from typing import Never
from uuid import UUID

from .actions import ChainResult, Round, Step, StepStatus, VirtualWriter, run_chain
from .config import ImapSettings
from .imap.client import ConnectionFactory, ImapClient, connect_aioimaplib
from .mail import Mail
from .matching import rules_by_folder
from .rules.models import Rule, RuleFile

logger = logging.getLogger(__name__)

MAX_INSPECTED = 5000
"""Mails looked at per account before the run stops and reports `truncated`."""


@dataclass
class DryRunEntry:
    mail: Mail
    """The mail as it is on the server, before the simulated steps."""
    chain: ChainResult
    """What the rules would do to it: the rounds in order, `moved_to` if it ends in another folder."""


@dataclass
class DryRunResult:
    rule: str
    inspected: int = 0
    truncated: bool = False
    entries: list[DryRunEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def merge(self, other: "DryRunResult") -> None:
        self.inspected += other.inspected
        self.truncated = self.truncated or other.truncated
        self.entries += other.entries
        self.errors += other.errors
    # end def
# end class


@dataclass(frozen=True)
class Cursor:
    """Where the next page of a dry run starts: a folder of an account, below `before_uid` (newest first)."""

    account_id: UUID
    folder: str | None = None
    """`None` means the first folder of the account."""
    before_uid: int | None = None


async def inspect(rules: list[Rule[Never]], rule_name: str, mail: Mail, result: DryRunResult) -> None:
    """Runs the chain on a copy of the mail and keeps the entry if the chosen rule is part of it."""
    result.inspected += 1
    chain = await run_chain(rules, replace(mail), VirtualWriter())
    chain.rounds = [Round(round_.rule, as_planned(round_.steps)) for round_ in chain.rounds]
    entry = DryRunEntry(mail, chain)
    if own_rounds(entry, rule_name):
        result.entries.append(entry)
    # end if
# end def


async def dry_run_page(
    settings: ImapSettings,
    rule_file: RuleFile[Never],
    rule_name: str,
    limit: int,
    cursor: Cursor | None = None,
    factory: ConnectionFactory = connect_aioimaplib,
) -> tuple[DryRunResult, Cursor | None]:
    """Looks at up to `limit` mails of one account, from the cursor on. The cursor for the next page is `None` when the account is done."""
    result = DryRunResult(rule=rule_name)
    account_id = settings.imap_account_id
    async with ImapClient(settings, factory) as client:
        by_folder = await rules_by_folder(client, rule_file, account_id)
        folders = [folder for folder, rules in by_folder.items() if any(rule.name == rule_name for rule in rules)]
        resumed = cursor is not None and cursor.folder in folders
        start = folders.index(cursor.folder) if cursor is not None and resumed else 0
        before = cursor.before_uid if cursor is not None and resumed else None
        for folder in folders[start:]:
            if result.inspected >= limit:
                return result, Cursor(account_id, folder)
            # end if
            uids = await client.list_uids(folder, before)
            batch = uids[: limit - result.inspected]
            for mail in await client.fetch_mails(account_id, folder, batch):
                await inspect(by_folder[folder], rule_name, mail, result)
            # end for
            if len(uids) > len(batch):
                return result, Cursor(account_id, folder, batch[-1])
            # end if
            before = None
        # end for
    # end async with
    return result, None
# end def


def own_rounds(entry: DryRunEntry, rule: str) -> list[Round]:
    return [round_ for round_ in entry.chain.rounds if round_.rule.name == rule]
# end def


def as_planned(steps: list[Step]) -> list[Step]:
    """A virtual writer reports `done`; for a dry run that reads as `planned`."""
    return [replace(step, status=StepStatus.planned) if step.status == StepStatus.done else step for step in steps]
# end def


async def dry_run_account(
    settings: ImapSettings,
    rule_file: RuleFile[Never],
    rule_name: str,
    factory: ConnectionFactory = connect_aioimaplib,
    max_inspected: int = MAX_INSPECTED,
) -> DryRunResult:
    """Simulates the rule file over the folders of one account that the chosen rule covers."""
    result = DryRunResult(rule=rule_name)
    account_id = settings.imap_account_id
    async with ImapClient(settings, factory) as client:
        by_folder = await rules_by_folder(client, rule_file, account_id)
        for folder, rules in by_folder.items():
            if not any(rule.name == rule_name for rule in rules):
                continue
            # end if
            async for page in client.iter_pages(account_id, folder, settings.imap_page_size):
                for mail in page:
                    if result.inspected >= max_inspected:
                        result.truncated = True
                        return result
                    # end if
                    await inspect(rules, rule_name, mail, result)
                # end for
            # end async for
        # end for
    # end async with
    return result
# end def


@dataclass(frozen=True)
class SummaryRow:
    type: str
    status: str
    count: int
    folder: str | None = None
    keyword: str | None = None
    reason: str | None = None


def summarize(result: DryRunResult) -> list[SummaryRow]:
    """How many mails get which step from the chosen rule, grouped by type, target and status."""
    counts: Counter[tuple[str, str, str | None, str | None, str | None]] = Counter()
    for entry in result.entries:
        for round_ in own_rounds(entry, result.rule):
            for step in round_.steps:
                folder, keyword = step.args.get("folder"), step.args.get("keyword")
                counts[(step.type, step.status.value, folder, keyword, step.reason)] += 1
            # end for
        # end for
    # end for
    return [
        SummaryRow(type=kind, status=status, count=count, folder=folder, keyword=keyword, reason=reason)
        for (kind, status, folder, keyword, reason), count in sorted(counts.items(), key=lambda item: (-item[1], item[0][0], item[0][1]))
    ]
# end def
