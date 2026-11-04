"""Rule actions: which steps a rule's actions come down to for a mail, and running them rule by rule.

Rules are processed in file order and the first matching rule wins.
If it changed the mail the rules are evaluated again from the top against the updated in-memory mail, without fetching it again.
A move ends the pass, because the mail is gone from the folder; the target folder's watcher sees it as new and starts from the top there.
A move to another account copies the whole mail there first (`APPEND`) and deletes it at the source only afterwards, so a failure in between leaves a duplicate and never loses the mail.
A writer decides what a step really does: `ImapWriter` changes the mailbox, `VirtualWriter` only does the bookkeeping (dry run).
"""

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field, replace
from enum import StrEnum
from typing import Any, Never, Protocol
from uuid import UUID

from aioimaplib import AioImapException

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
MAX_MOVES = 5
"""How often one mail (by `Message-ID`) may be moved by rules before further moves are refused as `move_loop`."""


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


@dataclass(frozen=True)
class MovedTo:
    """Where a moved mail is now. `uid` and `uidvalidity` are `None` if the server did not say (no `UIDPLUS`) or in a dry run."""

    account_id: UUID
    folder: str
    uid: int | None = None
    uidvalidity: int | None = None
# end class


@dataclass
class ChainResult:
    """What happened to one mail: the rounds in order, the mail as it ended up and where it went if it was moved."""

    mail: Mail
    rounds: list[Round] = field(default_factory=list)
    moved: MovedTo | None = None

    @property
    def moved_to(self) -> str | None:
        """The folder the mail was moved to."""
        return self.moved.folder if self.moved else None
    # end def
# end class


class ActionError(ImapError):
    """A step failed for a reason worth naming in the log. `moved` is set when the mail was copied but the source could not be deleted."""

    def __init__(self, reason: str, moved: MovedTo | None = None) -> None:
        super().__init__(reason)
        self.reason = reason
        self.moved = moved
    # end def
# end class


SettingsLookup = Callable[[UUID], Awaitable[ImapSettings | None]]
"""Finds the connection settings of another account by id, `None` if there is none."""

MoveGuard = Callable[[Mail], Awaitable[bool]]
"""Says whether rules may move this mail again, so rules sending a mail back and forth between folders or accounts stop."""

TargetClients = Callable[[UUID], Awaitable[ImapClient]]
"""Opens (or reuses) a client for another account, raising `ActionError("unknown_account")` if there is none."""


class Writer(Protocol):
    async def store_flags(self, mail: Mail, add: tuple[str, ...], remove: tuple[str, ...]) -> None: ...
    async def move(self, mail: Mail, folder: str, account_id: UUID | None = None) -> MovedTo: ...
# end class


class ImapWriter:
    """Applies steps to the mailbox through its own client, never through the connection of a watcher in `IDLE`."""

    def __init__(self, client: ImapClient, targets: TargetClients | None = None, allow_move: MoveGuard | None = None) -> None:
        self.client = client
        self.targets = targets
        self.allow_move = allow_move
    # end def

    async def store_flags(self, mail: Mail, add: tuple[str, ...], remove: tuple[str, ...]) -> None:
        await self.client.store_flags(mail.folder, mail.uid, add=add, remove=remove)
    # end def

    async def move(self, mail: Mail, folder: str, account_id: UUID | None = None) -> MovedTo:
        if self.allow_move is not None and not await self.allow_move(mail):
            raise ActionError("move_loop")
        # end if
        if account_id is None or account_id == mail.account_id:
            moved = await self.client.move(mail.folder, mail.uid, folder)
            return MovedTo(mail.account_id, folder, moved.uid, moved.uidvalidity)
        # end if
        return await self.move_across(mail, folder, account_id)
    # end def

    async def move_across(self, mail: Mail, folder: str, account_id: UUID) -> MovedTo:
        """Copies the mail to the other account, then deletes it here. Skips the copy if the target folder already has that `Message-ID` (a restarted move)."""
        if self.targets is None:
            raise ActionError("unknown_account")
        # end if
        target = await self.targets(account_id)
        message_id = str(mail.headers.get("Message-ID") or "").strip()
        existing = await target.find_message_id(folder, message_id) if message_id else None
        if existing is not None:
            moved = MovedTo(account_id, folder, existing, target.state.uidvalidity if target.state else None)
        else:
            raw = await self.client.fetch_raw(mail.folder, mail.uid)
            if raw is None:
                raise ActionError("gone")
            # end if
            appended = await target.append(folder, raw)
            moved = MovedTo(account_id, folder, appended.uid, appended.uidvalidity)
        # end if
        try:
            await self.client.delete(mail.folder, mail.uid)
        except ImapError as error:
            logger.warning("Copied %s/%s to account %s but could not delete the original: %s", mail.folder, mail.uid, account_id, error)
            raise ActionError("source_not_deleted", moved) from error
        # end try
        return moved
    # end def
# end class


class VirtualWriter:
    """Writes nothing, for the dry run."""

    async def store_flags(self, mail: Mail, add: tuple[str, ...], remove: tuple[str, ...]) -> None:
        return None
    # end def

    async def move(self, mail: Mail, folder: str, account_id: UUID | None = None) -> MovedTo:
        return MovedTo(account_id or mail.account_id, folder)
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
                if isinstance(action, FlagAction | KeywordAction):
                    args["value"] = wanted
                # end if
                if present == wanted:
                    steps.append(Step(action.type, args, StepStatus.noop, "already"))
                    continue
                # end if
                add, remove = ((name,), ()) if wanted else ((), (name,))
                steps.append(Step(action.type, args, StepStatus.planned, add=add, remove=remove))
                flags = with_flags(flags, add, remove)
            case MoveAction():
                args: dict[str, Any] = {"folder": action.folder}
                other_account = action.account_id is not None and action.account_id != mail.account_id
                if other_account:
                    args["account_id"] = str(action.account_id)
                # end if
                if move is not None:
                    steps.append(Step("move", args, StepStatus.skipped, "superseded"))
                elif action.folder == mail.folder and not other_account:
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


async def execute_steps(steps: list[Step], mail: Mail, writer: Writer) -> tuple[list[Step], MovedTo | None]:
    """Runs the planned steps. Stops at the first error. Updates `mail.flags` as steps succeed. Returns the steps and where a move put the mail."""
    result: list[Step] = []
    moved: MovedTo | None = None
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
                account = step.args.get("account_id")
                moved = await writer.move(mail, str(step.args["folder"]), UUID(account) if account else None)
            else:
                await writer.store_flags(mail, step.add, step.remove)
                mail.flags = with_flags(mail.flags, step.add, step.remove)
            # end if
        except ImapError as error:
            logger.warning("Step %s on %s/%s failed: %s", step.type, mail.folder, mail.uid, error)
            failed = True
            if isinstance(error, ActionError):
                moved = error.moved
            # end if
            result.append(replace(step, status=StepStatus.error, reason=error.reason if isinstance(error, ActionError) else str(error)))
            continue
        # end try
        result.append(replace(step, status=StepStatus.done))
    # end for
    return result, moved
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
        steps, moved = await execute_steps(plan_steps(winner, mail), mail, writer)
        result.rounds.append(Round(winner, steps))
        if moved is not None:
            result.moved = moved
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


class ActionRunner:
    """Runs the rules for real over single mails, on one connection of its own that opens with the first mail.

    Every mail is fetched fresh first (one cheap `FETCH`): the flags of a mail from a watcher may be stale, and its body loader would
    use the connection that sits in `IDLE`.
    """

    def __init__(
        self,
        settings: ImapSettings,
        rule_file: RuleFile[Never],
        factory: ConnectionFactory = connect_aioimaplib,
        lookup: SettingsLookup | None = None,
        allow_move: MoveGuard | None = None,
    ) -> None:
        self.settings = settings
        self.rule_file = rule_file
        self.factory = factory
        self.lookup = lookup
        self.allow_move = allow_move
        self.client: ImapClient | None = None
        self.target_clients: dict[UUID, ImapClient] = {}
        self.by_folder: dict[str, list[Rule[Never]]] = {}
    # end def

    async def __aenter__(self) -> "ActionRunner":
        return self
    # end def

    async def __aexit__(self, *exc: object) -> None:
        await self.close()
    # end def

    async def close(self) -> None:
        clients, self.target_clients = list(self.target_clients.values()), {}
        client, self.client = self.client, None
        for item in [*clients, *([client] if client is not None else [])]:
            await item.close()
        # end for
    # end def

    async def target(self, account_id: UUID) -> ImapClient:
        """A client for another account, opened once and kept until `close()`."""
        if account_id not in self.target_clients:
            settings = await self.lookup(account_id) if self.lookup is not None else None
            if settings is None:
                raise ActionError("unknown_account")
            # end if
            client = ImapClient(settings, self.factory)
            await client.connect()
            self.target_clients[account_id] = client
        # end if
        return self.target_clients[account_id]
    # end def

    async def open(self) -> ImapClient:
        if self.client is None:
            client = ImapClient(self.settings, self.factory)
            await client.connect()
            self.client = client
            self.by_folder = await rules_by_folder(client, self.rule_file, self.settings.imap_account_id)
        # end if
        return self.client
    # end def

    async def run(self, mail: Mail) -> ChainResult | None:
        """The result for the mail, or `None` if it is gone. A broken connection is dropped, so the next call reconnects."""
        try:
            client = await self.open()
            fresh = await client.fetch_message(self.settings.imap_account_id, mail.folder, mail.uid)
            if fresh is None:
                return None
            # end if
            return await run_chain(rules_for_mail(self.by_folder, fresh), fresh, ImapWriter(client, self.target, self.allow_move))
        except (ImapError, AioImapException, OSError, TimeoutError):
            await self.close()
            raise
        # end try
    # end def
# end class


async def apply_actions(
    settings: ImapSettings,
    rule_file: RuleFile[Never],
    mails: list[Mail],
    factory: ConnectionFactory = connect_aioimaplib,
    lookup: SettingsLookup | None = None,
) -> list[ChainResult]:
    """Runs the rules over the given mails of one account for real."""
    async with ActionRunner(settings, rule_file, factory, lookup) as runner:
        results = [await runner.run(mail) for mail in mails]
    # end async with
    return [result for result in results if result is not None]
# end def
