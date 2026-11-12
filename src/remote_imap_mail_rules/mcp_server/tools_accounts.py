"""Tools for the mail accounts and their folders. Passwords have their own scopes."""

from typing import Any
from uuid import UUID

from fastapi import BackgroundTasks, FastAPI
from mcp.server.mcpserver.exceptions import ToolError

from ..db import accounts as repository
from ..db.crypto import CryptoError
from ..server.api import accounts as accounts_api, mail as mail_api
from .context import api_call, db_session, has_scope, request_of
from .scoped import ScopedServer
from .scopes import Scope


def register(server: ScopedServer, app: FastAPI) -> None:
    async def run_after(background: BackgroundTasks) -> None:
        await background()
    # end def

    @server.scoped_tool(Scope.accounts_read, description="All mail accounts: id, name, host, port, username, login state. Never the password.")
    async def list_accounts() -> dict[str, Any]:
        async with db_session(app) as session:
            out = await api_call(accounts_api.list_accounts(request_of(app), session))
        # end with
        return {"accounts": [account.model_dump(mode="json") for account in out]}
    # end def

    @server.scoped_tool(Scope.accounts_read, description="One mail account, by id.")
    async def get_account(account_id: UUID) -> dict[str, Any]:
        async with db_session(app) as session:
            out = await api_call(accounts_api.get_account(request_of(app), account_id, session))
        # end with
        return out.model_dump(mode="json")
    # end def

    @server.scoped_tool(
        Scope.accounts_write, Scope.accounts_password_write,
        description="Creates an account (the id is generated unless given). Needs the password, so it needs accounts.password:write too.",
    )
    async def create_account(
        name: str, host: str, username: str, password: str, port: int = 993, ssl: bool = True, id: UUID | None = None,
        page_size: int = 50, poll_interval: float = 60.0,
    ) -> dict[str, Any]:
        body = accounts_api.AccountCreate(
            id=id, name=name, host=host, port=port, ssl=ssl, username=username, password=password, page_size=page_size, poll_interval=poll_interval
        )
        background = BackgroundTasks()
        async with db_session(app) as session:
            out = await api_call(accounts_api.create_account(request_of(app), background, body, session))
        # end with
        await run_after(background)
        return out.model_dump(mode="json")
    # end def

    @server.scoped_tool(
        Scope.accounts_write,
        description="Changes an account: pass the account's full settings as `values` (name, host, port, ssl, username, page_size, poll_interval, "
        "optional new id). A new id is rewritten into the rules. A `password` in the values needs accounts.password:write.",
    )
    async def update_account(account_id: UUID, values: dict[str, Any]) -> dict[str, Any]:
        if values.get("password") is not None and not has_scope(Scope.accounts_password_write):
            raise ToolError("Setting a password needs the scope accounts.password:write.")
        # end if
        background = BackgroundTasks()
        async with db_session(app) as session:
            current = await api_call(accounts_api.get_account(request_of(app), account_id, session))
            merged = {**current.model_dump(include=set(accounts_api.AccountIn.model_fields)), **values}
            body = accounts_api.AccountUpdate.model_validate(merged)
            out = await api_call(accounts_api.update_account(request_of(app), background, account_id, body, session))
        # end with
        await run_after(background)
        return out.model_dump(mode="json")
    # end def

    @server.scoped_tool(Scope.accounts_delete, description="Deletes an account; refused while a rule still has a location in it.")
    async def delete_account(account_id: UUID) -> str:
        background = BackgroundTasks()
        async with db_session(app) as session:
            await api_call(accounts_api.delete_account(request_of(app), background, account_id, session))
        # end with
        await run_after(background)
        return "deleted"
    # end def

    @server.scoped_tool(Scope.accounts_password_read, description="The stored password of an account, decrypted.")
    async def get_account_password(account_id: UUID) -> dict[str, str]:
        async with db_session(app) as session:
            account = await repository.get_account(session, account_id)
            if account is None:
                raise ToolError("No such account.")
            # end if
            try:
                password = repository.imap_settings(account, app.state.settings.secret_key).imap_password.get_secret_value()
            except CryptoError as e:
                raise ToolError(str(e)) from e
            # end try
        # end with
        return {"password": password}
    # end def

    @server.scoped_tool(Scope.accounts_password_write, description="Sets a new password for an account; the login history starts over.")
    async def set_account_password(account_id: UUID, password: str) -> str:
        background = BackgroundTasks()
        async with db_session(app) as session:
            current = await api_call(accounts_api.get_account(request_of(app), account_id, session))
            body = accounts_api.AccountUpdate.model_validate({**current.model_dump(include=set(accounts_api.AccountIn.model_fields)), "password": password})
            await api_call(accounts_api.update_account(request_of(app), background, account_id, body, session))
        # end with
        await run_after(background)
        return "password set"
    # end def

    @server.scoped_tool(Scope.folders_read, description="The folder tree of an account as the mail server lists it, with message counts.")
    async def list_folders(account_id: UUID) -> dict[str, Any]:
        async with db_session(app) as session:
            folders = await api_call(mail_api.list_folders(request_of(app), account_id, session))
        # end with
        return {"folders": [folder.model_dump(mode="json") for folder in folders]}
    # end def
# end def
