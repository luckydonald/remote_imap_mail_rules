"""Endpoints of the account management, mounted at `/api/accounts`."""

from collections.abc import AsyncIterator
from datetime import datetime
from uuid import UUID

from typing import Literal

import aioimaplib
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field, SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from ...config import ImapSettings
from ...db import accounts as repository
from ...db.crypto import CryptoError
from ...db.engine import iter_session
from ...db.models import Account
from ...db.models.account import as_utc
from ...imap.client import ConnectionFactory, ImapClient, ImapError, ImapLoginError
from .. import rules_file
from ..rules_store import RulesStore, replace_account_id, rules_referencing
from ..settings import ServerSettings

router = APIRouter()


class AccountIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    host: str = Field(min_length=1, max_length=255)
    port: int = Field(default=993, ge=1, le=65535)
    ssl: bool = True
    username: str = Field(min_length=1, max_length=255)
    page_size: int = Field(default=50, ge=1)
    poll_interval: float = Field(default=60.0, gt=0)


class AccountCreate(AccountIn):
    id: UUID | None = Field(default=None, description="Omitted generates one.")
    password: str = Field(min_length=1)


class AccountUpdate(AccountIn):
    id: UUID | None = Field(default=None, description="Omitted keeps the id; a new one is written into the rules too.")
    password: str | None = Field(default=None, description="Omitted keeps the stored password.")


class AccountCheck(AccountIn):
    id: UUID | None = Field(default=None, description="The stored account whose password is used when none is given.")
    password: str | None = Field(default=None, min_length=1, description="Omitted uses the stored password of `id`.")


class AccountCheckResult(BaseModel):
    ok: bool
    kind: Literal["ok", "rejected", "unreachable", "timeout"]
    message: str


class AccountOut(AccountIn):
    id: UUID
    has_password: bool = True
    env_differs: list[str] = Field(default_factory=list, description="Fields that differ from the environment's account.")
    auth_updated_at: datetime | None = Field(default=None, description="When the username or password were last set.")
    auth_failed_at: datetime | None = Field(default=None, description="The last rejected login, since the credentials were set.")
    auth_fail_count: int = Field(default=0, description="Rejected logins since the credentials were set.")
    auth_ok_at: datetime | None = Field(default=None, description="The last working login, since the credentials were set.")
    auth_last_error: str | None = Field(default=None, description="The server's answer to the last rejected login.")
    needs_check: bool = Field(default=False, description="The last login was rejected and none worked since.")


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    async for session in iter_session(request.app.state.session_factory):
        yield session
    # end for
# end def


def get_settings(request: Request) -> ServerSettings:
    settings: ServerSettings = request.app.state.settings
    return settings
# end def


def to_out(request: Request, account: Account) -> AccountOut:
    env: ImapSettings | None = request.app.state.env_account
    differs: list[str] = []
    if env is not None and env.imap_account_id == account.id:
        differs = repository.env_differences(account, env, get_settings(request).secret_key)
    # end if
    return AccountOut(
        id=account.id,
        name=account.name,
        host=account.host,
        port=account.port,
        ssl=account.ssl,
        username=account.username,
        page_size=account.page_size,
        poll_interval=account.poll_interval,
        has_password=bool(account.password_encrypted),
        env_differs=differs,
        auth_updated_at=as_utc(account.auth_updated_at),
        auth_failed_at=None if account.auth_failed_at is None else as_utc(account.auth_failed_at),
        auth_fail_count=account.auth_fail_count,
        auth_ok_at=None if account.auth_ok_at is None else as_utc(account.auth_ok_at),
        auth_last_error=account.auth_last_error,
        needs_check=account.needs_check,
    )
# end def


async def find(session: AsyncSession, account_id: UUID) -> Account:
    account = await repository.get_account(session, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="No such account.")
    # end if
    return account
# end def


def no_key() -> HTTPException:
    return HTTPException(status_code=503, detail="SECRET_KEY is not set (or invalid), so passwords cannot be stored.")
# end def


@router.get("")
async def list_accounts(request: Request, session: AsyncSession = Depends(get_session)) -> list[AccountOut]:
    return [to_out(request, account) for account in await repository.list_accounts(session)]
# end def


@router.post("", status_code=201)
async def create_account(request: Request, background: BackgroundTasks, body: AccountCreate, session: AsyncSession = Depends(get_session)) -> AccountOut:
    values = body.model_dump()
    account_id = values.pop("id")
    if account_id is not None and await repository.get_account(session, account_id) is not None:
        raise HTTPException(status_code=409, detail=["An account with this id exists already."])
    # end if
    try:
        account = await repository.create_account(session, get_settings(request).secret_key, account_id=account_id, **values)
    except CryptoError as e:
        raise no_key() from e
    # end try
    background.add_task(request.app.state.watcher.restart)
    return to_out(request, account)
# end def


@router.post("/check")
async def check_account(request: Request, body: AccountCheck, session: AsyncSession = Depends(get_session)) -> AccountCheckResult:
    """Tries the login with the form's values. Always 200, a failed login is an expected result and not a 5xx for Sentry.

    Uses the plain connection factory, so the result is not noted on the account's login history.
    """
    secret_key = get_settings(request).secret_key
    password = body.password
    if password is None:
        account = None if body.id is None else await repository.get_account(session, body.id)
        if account is None:
            raise HTTPException(status_code=422, detail=["A password is needed."])
        # end if
        try:
            password = repository.imap_settings(account, secret_key).imap_password.get_secret_value()
        except CryptoError as e:
            raise no_key() from e
        # end try
    # end if
    imap_settings = ImapSettings(
        _env_file=None,  # type: ignore[call-arg]
        imap_account_id=body.id or UUID(int=0),
        imap_host=body.host,
        imap_port=body.port,
        imap_ssl=body.ssl,
        imap_username=body.username,
        imap_password=SecretStr(password),
    )
    factory: ConnectionFactory = request.app.state.raw_imap_factory
    try:
        async with ImapClient(imap_settings, factory):
            pass
        # end async with
    except TimeoutError:
        return AccountCheckResult(ok=False, kind="timeout", message="The mail server did not answer in time.")
    except ImapLoginError as e:
        if not e.transient:
            return AccountCheckResult(ok=False, kind="rejected", message=e.server_text)
        # end if
        return AccountCheckResult(ok=False, kind="unreachable", message=f"The mail server failed: {e.server_text}")
    except (ImapError, aioimaplib.AioImapException, OSError) as e:
        return AccountCheckResult(ok=False, kind="unreachable", message=f"The mail server failed: {e}")
    # end try
    return AccountCheckResult(ok=True, kind="ok", message="Login works.")
# end def


@router.get("/{account_id}")
async def get_account(request: Request, account_id: UUID, session: AsyncSession = Depends(get_session)) -> AccountOut:
    return to_out(request, await find(session, account_id))
# end def


@router.put("/{account_id}")
async def update_account(request: Request, background: BackgroundTasks, account_id: UUID, body: AccountUpdate, session: AsyncSession = Depends(get_session)) -> AccountOut:
    account = await find(session, account_id)
    values = body.model_dump()
    new_id = values.pop("id")
    changed_id = new_id is not None and new_id != account_id
    if changed_id and await repository.get_account(session, new_id) is not None:
        raise HTTPException(status_code=409, detail=["An account with this id exists already."])
    # end if
    if changed_id:
        # First the rules, as they can be refused; nothing references an account row, so the order does not matter otherwise.
        try:
            rewritten = await replace_account_id(request.app.state.rules_store, account_id, new_id)
        except rules_file.InvalidRules as e:
            raise HTTPException(status_code=422, detail=e.messages) from e
        # end try
        if rewritten:
            background.add_task(request.app.state.git.auto)
        # end if
    # end if
    try:
        await repository.update_account(session, get_settings(request).secret_key, account, new_id=new_id, **values)
    except CryptoError as e:
        raise no_key() from e
    # end try
    background.add_task(request.app.state.watcher.restart)
    return to_out(request, account)
# end def


@router.delete("/{account_id}", status_code=204)
async def delete_account(request: Request, background: BackgroundTasks, account_id: UUID, session: AsyncSession = Depends(get_session)) -> None:
    account = await find(session, account_id)
    store: RulesStore = request.app.state.rules_store
    names = await rules_referencing(store, account_id)
    if names:
        raise HTTPException(status_code=409, detail=[f"Still used by the rule: {name}" for name in names])
    # end if
    await repository.delete_account(session, account)
    background.add_task(request.app.state.watcher.restart)
# end def
