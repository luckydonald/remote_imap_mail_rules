"""Dry run of a rule and "Run now", mounted at `/api/dry-run`.

A dry run never writes to a mailbox or to the log. It works for the rule file in the request (the editor's unsaved text) or, without one,
for the stored file. "Run now" only works on the stored file and only when the server applies rules (`ACTIONS_ENABLED`).
"""

from typing import Any, Never
from uuid import UUID

import aioimaplib
import yaml
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from ...actions import ActionRunner, ChainResult, Round
from ...config import ImapSettings
from ...db import accounts as account_repository
from ...db.crypto import CryptoError
from ...dry_run import Cursor, DryRunEntry, DryRunResult, dry_run_account, dry_run_page, own_rounds, summarize
from ...imap.client import ConnectionFactory, ImapError
from ...rules.loader import parse_rules
from ...rules.models import Rule, RuleFile
from ..mail_view import SummaryOut, summary_out
from ..rules_store import RulesStore
from ..settings import ServerSettings
from .accounts import get_session

router = APIRouter()

FAILURES = (ImapError, aioimaplib.AioImapException, OSError, TimeoutError)


PAGE_SIZE = 200
"""Mails looked at per request, so a page comes back quickly."""


class CursorModel(BaseModel):
    account_id: UUID
    folder: str | None = None
    before_uid: int | None = Field(default=None, ge=1)


class DryRunIn(BaseModel):
    rule: str = Field(min_length=1, description="Name of the rule.")
    cursor: CursorModel | None = Field(default=None, description="The `next` of the previous page; the first page if unset.")
    limit: int = Field(default=PAGE_SIZE, ge=1, le=1000, description="How many mails to look at in this page.")
    yaml: str | None = Field(default=None, description="The rule file to simulate, e.g. the editor's unsaved text; the stored file if unset.")


class RunIn(BaseModel):
    rule: str = Field(min_length=1)


class StepOut(BaseModel):
    type: str
    status: str
    reason: str | None
    args: dict[str, Any]


class RoundOut(BaseModel):
    rule: str
    steps: list[StepOut]


class SummaryRowOut(BaseModel):
    type: str
    status: str
    count: int
    folder: str | None
    keyword: str | None
    reason: str | None


class AffectedMail(SummaryOut):
    account_id: UUID
    folder: str
    rounds: list[RoundOut]
    moved_to: str | None


class DryRunOut(BaseModel):
    rule: str
    actions_enabled: bool
    inspected: int
    """Mails looked at in this page."""
    affected: int
    """Of those, the mails the rule does something to."""
    summary: list[SummaryRowOut]
    mails: list[AffectedMail]
    errors: list[str]
    next: CursorModel | None
    """Pass it back to get the next page, `None` when everything was looked at."""


class RunOut(BaseModel):
    applied: int
    steps: dict[str, int]
    errors: list[str]


def round_out(round_: Round) -> RoundOut:
    return RoundOut(
        rule=round_.rule.name,
        steps=[StepOut(type=step.type, status=step.status.value, reason=step.reason, args=step.args) for step in round_.steps],
    )
# end def


def affected_mail(entry: DryRunEntry) -> AffectedMail:
    mail = entry.mail
    return AffectedMail(
        **summary_out(mail).model_dump(),
        account_id=mail.account_id,
        folder=mail.folder,
        rounds=[round_out(round_) for round_ in entry.chain.rounds],
        moved_to=entry.chain.moved_to,
    )
# end def


async def load_rule_file(request: Request, text: str | None) -> RuleFile[Never]:
    if text is None:
        store: RulesStore = request.app.state.rules_store
        text = await store.read_text()
        if text is None:
            raise HTTPException(status_code=404, detail="There are no rules yet.")
        # end if
    # end if
    try:
        return parse_rules(text)
    except yaml.YAMLError as e:
        raise HTTPException(status_code=422, detail=[f"YAML: {e}"]) from e
    except ValidationError as e:
        raise HTTPException(status_code=422, detail=[f"{'.'.join(str(part) for part in err['loc'])}: {err['msg']}" for err in e.errors()]) from e
    # end try
# end def


def find_rule(rule_file: RuleFile[Never], rule_name: str) -> Rule[Never]:
    rule = next((rule for rule in rule_file.rules if rule.name == rule_name), None)
    if rule is None:
        raise HTTPException(status_code=404, detail=f"There is no rule named {rule_name!r}.")
    # end if
    return rule
# end def


async def simulate(request: Request, session: AsyncSession, rule_file: RuleFile[Never], rule_name: str) -> tuple[DryRunResult, list[ImapSettings]]:
    """Dry runs the rule on every stored account it has a location for. Accounts that fail are reported, not raised."""
    rule = find_rule(rule_file, rule_name)
    settings: ServerSettings = request.app.state.settings
    factory: ConnectionFactory = request.app.state.imap_factory
    total = DryRunResult(rule=rule_name)
    used: list[ImapSettings] = []
    for account_id in dict.fromkeys(location.account_id for location in rule.locations):
        account = await account_repository.get_account(session, account_id)
        if account is None:
            total.errors.append(f"Account {account_id} is not registered in the server.")
            continue
        # end if
        try:
            imap_settings = account_repository.imap_settings(account, settings.secret_key)
        except CryptoError as e:
            total.errors.append(f"Account {account.name}: {e}")
            continue
        # end try
        try:
            total.merge(await dry_run_account(imap_settings, rule_file, rule_name, factory))
            used.append(imap_settings)
        except FAILURES as e:
            total.errors.append(f"Account {account.name}: the mail server failed: {e}")
        # end try
    # end for
    return total, used
# end def


async def simulate_page(request: Request, session: AsyncSession, rule_file: RuleFile[Never], body: DryRunIn) -> tuple[DryRunResult, Cursor | None]:
    """The next `limit` mails of the rule's accounts, in the order of its locations, and where to go on."""
    rule = find_rule(rule_file, body.rule)
    settings: ServerSettings = request.app.state.settings
    factory: ConnectionFactory = request.app.state.imap_factory
    account_ids = list(dict.fromkeys(location.account_id for location in rule.locations))
    cursor = Cursor(body.cursor.account_id, body.cursor.folder, body.cursor.before_uid) if body.cursor else None
    if cursor is not None and cursor.account_id not in account_ids:
        cursor = None
    # end if
    total = DryRunResult(rule=body.rule)
    for index in range(account_ids.index(cursor.account_id) if cursor is not None else 0, len(account_ids)):
        account_id = account_ids[index]
        if total.inspected >= body.limit:
            return total, Cursor(account_id)
        # end if
        account = await account_repository.get_account(session, account_id)
        if account is None:
            total.errors.append(f"Account {account_id} is not registered in the server.")
            continue
        # end if
        try:
            imap_settings = account_repository.imap_settings(account, settings.secret_key)
        except CryptoError as e:
            total.errors.append(f"Account {account.name}: {e}")
            continue
        # end try
        try:
            page, following = await dry_run_page(imap_settings, rule_file, body.rule, body.limit - total.inspected, cursor, factory)
        except FAILURES as e:
            total.errors.append(f"Account {account.name}: the mail server failed: {e}")
            cursor = None
            continue
        # end try
        cursor = None
        total.merge(page)
        if following is not None:
            return total, following
        # end if
    # end for
    return total, None
# end def


@router.post("")
async def post_dry_run(request: Request, body: DryRunIn, session: AsyncSession = Depends(get_session)) -> DryRunOut:
    """One page of the dry run: the next `limit` mails are looked at, the summary and the list are for this page only."""
    rule_file = await load_rule_file(request, body.yaml)
    result, following = await simulate_page(request, session, rule_file, body)
    return DryRunOut(
        rule=body.rule,
        actions_enabled=request.app.state.settings.actions_enabled,
        inspected=result.inspected,
        affected=len(result.entries),
        summary=[SummaryRowOut(**row.__dict__) for row in summarize(result)],
        mails=[affected_mail(entry) for entry in result.entries],
        errors=result.errors,
        next=CursorModel(account_id=following.account_id, folder=following.folder, before_uid=following.before_uid) if following else None,
    )
# end def


@router.post("/run")
async def post_run(request: Request, body: RunIn, session: AsyncSession = Depends(get_session)) -> RunOut:
    """Applies the rule to the mails the dry run finds, like the watcher does, and writes the `action` entries."""
    settings: ServerSettings = request.app.state.settings
    if not settings.actions_enabled:
        raise HTTPException(status_code=409, detail="actions_disabled")
    # end if
    rule_file = await load_rule_file(request, None)
    result, used = await simulate(request, session, rule_file, body.rule)
    factory: ConnectionFactory = request.app.state.imap_factory
    watcher = request.app.state.watcher
    errors = list(result.errors)
    steps: dict[str, int] = {}
    applied = 0
    for imap_settings in used:
        entries = [entry for entry in result.entries if entry.mail.account_id == imap_settings.imap_account_id and own_rounds(entry, body.rule)]
        async with ActionRunner(imap_settings, rule_file, factory, watcher.lookup_settings) as runner:
            for entry in entries:
                try:
                    chain: ChainResult | None = await runner.run(entry.mail)
                except FAILURES as e:
                    errors.append(f"{entry.mail.folder} #{entry.mail.uid}: {e}")
                    continue
                # end try
                if chain is None:
                    continue
                # end if
                await watcher.write_actions(session, chain)
                await session.commit()
                applied += 1
                for round_ in chain.rounds:
                    for step in round_.steps:
                        steps[step.status.value] = steps.get(step.status.value, 0) + 1
                    # end for
                # end for
            # end for
        # end async with
    # end for
    return RunOut(applied=applied, steps=steps, errors=errors)
# end def
