"""Rule actions: which steps a rule's actions come down to for a mail, and running them rule by rule.

Rules are processed in file order and the first matching rule wins.
If it changed the mail the rules are evaluated again from the top against the updated in-memory mail, without fetching it again.
A move ends the pass, because the mail is gone from the folder; the target folder's watcher sees it as new and starts from the top there.
A writer decides what a step really does: `ImapWriter` changes the mailbox, `VirtualWriter` only does the bookkeeping (dry run).
"""

import logging
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Never, Protocol
from uuid import UUID

from .config import ImapSettings
from .imap.client import ConnectionFactory, ImapClient, ImapError, connect_aioimaplib
from .mail import Mail
from .matching import rules_by_folder
from .rules.evaluate import evaluate
from .rules.models import FlagAction, KeywordAction, MarkReadAction, MarkUnreadAction, MoveAction, Rule, RuleFile

logger = logging.getLogger(__name__)

SEEN = "\\Seen"
FLAGGED = "\\Flagged"
MAX_ROUNDS = 10
"""Hard cap on how often the rules are evaluated again for one mail."""


class StepStatus(StrEnum):
    planned = "planned"
    done = "done"
    noop = "noop"
    skipped = "skipped"
    error = "error"
# end class


@dataclass(frozen=True)
class Step:
    """One thing a rule does to a mail. `args` is what ends up in the log, e.g. `{"folder": "Archive"}`."""

    type: str
    args: dict[str, Any] = field(default_factory=dict)
    status: StepStatus = StepStatus.planned
    reason: str | None = None
    add: tuple[str, ...] = ()
    remove: tuple[str, ...] = ()

    @property
    def changes_mail(self) -> bool:
        return self.status == StepStatus.done
    # end def
# end class


@dataclass(frozen=True)
class Round:
    rule: Rule[Never]
    steps: list[Step]
# end class


@dataclass
class ChainResult:
    """What happened to one mail: the rounds in order and the mail as it ended up."""

    mail: Mail
    rounds: list[Round] = field(default_factory=list)
    moved_to: str | None = None
# end class


class Writer(Protocol):
    async def store_flags(self, mail: Mail, add: tuple[str, ...], remove: tuple[str, ...]) -> None: ...
    async def move(self, mail: Mail, folder: str) -> None: ...
# end class


class ImapWriter:
    """Applies steps to the mailbox through its own client, never through the connection of a watcher in `IDLE`."""

    def __init__(self, client: ImapClient) -> None:
        self.client = client
    # end def

    async def store_flags(self, mail: Mail, add: tuple[str, ...], remove: tuple[str, ...]) -> None:
        await self.client.store_flags(mail.folder, mail.uid, add=add, remove=remove)
    # end def

    async def move(self, mail: Mail, folder: str) -> None:
        await self.client.move(mail.folder, mail.uid, folder)
    # end def
# end class


class VirtualWriter:
    """Writes nothing, for the dry run."""

    async def store_flags(self, mail: Mail, add: tuple[str, ...], remove: tuple[str, ...]) -> None:
        return None
    # end def

    async def move(self, mail: Mail, folder: str) -> None:
        return None
    # end def
# end class


def with_flags(flags: frozenset[str], add: tuple[str, ...], remove: tuple[str, ...]) -> frozenset[str]:
    removed = {flag.lower() for flag in remove}
    return frozenset(flag for flag in flags if flag.lower() not in removed) | frozenset(add)
# end def


def has(flags: frozenset[str], flag: str) -> bool:
    return flag.lower() in {existing.lower() for existing in flags}
# end def


def plan_steps(rule: Rule[Never], mail: Mail) -> list[Step]:
    """The steps of the rule's actions for this mail, `noop` where the mail is already as wanted, a move always last.

    Actions are planned one after another on a local copy of the flags, so `mark_read` followed by `mark_unread` ends as unread.
    Only the first `move` counts, later ones are skipped.
    """
    flags = mail.flags
    steps: list[Step] = []
    move: Step | None = None
    for action in rule.actions:
        match action:
            case MarkReadAction() | MarkUnreadAction() | FlagAction() | KeywordAction():
                name, wanted = flag_change(action)
                present = has(flags, name)
                args: dict[str, Any] = {"keyword": name} if isinstance(action, KeywordAction) else {}
                if present == wanted:
                    steps.append(Step(action.type, args, StepStatus.noop, "already"))
                    continue
                # end if
                add, remove = ((name,), ()) if wanted else ((), (name,))
                steps.append(Step(action.type, args, StepStatus.planned, add=add, remove=remove))
                flags = with_flags(flags, add, remove)
            case MoveAction():
                args: dict[str, Any] = {"folder": action.folder}
                if action.account_id is not None and action.account_id != mail.account_id:
                    args["account_id"] = str(action.account_id)
                    steps.append(Step("move", args, StepStatus.skipped, "cross_account_not_supported"))
                elif move is not None:
                    steps.append(Step("move", args, StepStatus.skipped, "superseded"))
                elif action.folder == mail.folder:
                    steps.append(Step("move", args, StepStatus.noop, "already"))
                else:
                    move = Step("move", args)
                # end if
        # end match
    # end for
    return [*steps, move] if move is not None else steps
# end def


def flag_change(action: MarkReadAction | MarkUnreadAction | FlagAction[Never] | KeywordAction[Never]) -> tuple[str, bool]:
    """The flag an action touches and whether it should be present afterwards."""
    match action:
        case MarkReadAction():
            return SEEN, True
        case MarkUnreadAction():
            return SEEN, False
        case FlagAction():
            return FLAGGED, action.value
        case KeywordAction():
            return action.keyword, action.value
    # end match
# end def


async def execute_steps(steps: list[Step], mail: Mail, writer: Writer) -> tuple[list[Step], str | None]:
    """Runs the planned steps. Stops at the first error. Updates `mail.flags` as steps succeed. Returns the steps and the target folder of a move."""
    result: list[Step] = []
    moved_to: str | None = None
    failed = False
    for step in steps:
        if step.status != StepStatus.planned:
            result.append(step)
            continue
        # end if
        if failed:
            result.append(replace(step, status=StepStatus.skipped, reason="earlier_error"))
            continue
        # end if
        try:
            if step.type == "move":
                await writer.move(mail, str(step.args["folder"]))
                moved_to = str(step.args["folder"])
            else:
                await writer.store_flags(mail, step.add, step.remove)
                mail.flags = with_flags(mail.flags, step.add, step.remove)
            # end if
        except ImapError as error:
            logger.warning("Step %s on %s/%s failed: %s", step.type, mail.folder, mail.uid, error)
            failed = True
            result.append(replace(step, status=StepStatus.error, reason=str(error)))
            continue
        # end try
        result.append(replace(step, status=StepStatus.done))
    # end for
    return result, moved_to
# end def


async def first_match(rules: list[Rule[Never]], mail: Mail) -> Rule[Never] | None:
    for rule in rules:
        if await evaluate(rule.when, mail):
            return rule
        # end if
    # end for
    return None
# end def


async def run_chain(rules: list[Rule[Never]], mail: Mail, writer: Writer, max_rounds: int = MAX_ROUNDS) -> ChainResult:
    """Applies the first matching rule, then evaluates the rules again from the top on the updated mail, until nothing changes.

    `mail` is changed in place (its `flags`), pass a copy for a dry run.
    """
    result = ChainResult(mail=mail)
    ran: set[str] = set()
    for _ in range(max_rounds):
        winner = await first_match(rules, mail)
        if winner is None or winner.name in ran:
            break
        # end if
        ran.add(winner.name)
        steps, moved_to = await execute_steps(plan_steps(winner, mail), mail, writer)
        result.rounds.append(Round(winner, steps))
        if moved_to is not None:
            result.moved_to = moved_to
            break
        # end if
        if not any(step.changes_mail for step in steps):
            break
        # end if
    # end for
    return result
# end def


def rules_for_mail(by_folder: dict[str, list[Rule[Never]]], mail: Mail) -> list[Rule[Never]]:
    return by_folder.get(mail.folder, [])
# end def


async def apply_actions(settings: ImapSettings, rule_file: RuleFile[Never], mails: list[Mail], factory: ConnectionFactory = connect_aioimaplib) -> list[ChainResult]:
    """Runs the rules over the given mails of one account for real.

    Every mail is fetched fresh first (one cheap `FETCH`) through the executor's own connection: the flags may be stale, and the body
    loader of a mail from a watcher would use the connection that sits in `IDLE`.
    """
    results: list[ChainResult] = []
    account_id: UUID = settings.imap_account_id
    async with ImapClient(settings, factory) as client:
        by_folder = await rules_by_folder(client, rule_file, account_id)
        writer = ImapWriter(client)
        for stale in mails:
            fresh = await client.fetch_message(account_id, stale.folder, stale.uid)
            if fresh is None:
                continue
            # end if
            results.append(await run_chain(rules_for_mail(by_folder, fresh), fresh, writer))
        # end for
    # end async with
    return results
# end def
