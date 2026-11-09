"""Opens an IMAP connection for one request and turns IMAP failures into HTTP errors."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID

import aioimaplib
from fastapi import HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import accounts as repository
from ..db.crypto import CryptoError
from ..imap.client import ConnectionFactory, ImapClient, ImapError, ImapLoginError
from .settings import ServerSettings


@asynccontextmanager
async def imap_session(request: Request, session: AsyncSession, account_id: UUID) -> AsyncIterator[ImapClient]:
    """404 for an unknown account, 503 if the password cannot be decrypted, 424 if the server rejects the login, 502 / 504 if it fails otherwise.

    424 and not a 5xx: a wrong password is the account's setup, and the Sentry integrations report every 5xx `HTTPException`. The login itself is
    noted on the account by `login_log.recording_factory`.
    """
    settings: ServerSettings = request.app.state.settings
    factory: ConnectionFactory = request.app.state.imap_factory
    account = await repository.get_account(session, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="No such account.")
    # end if
    try:
        imap_settings = repository.imap_settings(account, settings.secret_key)
    except CryptoError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    # end try
    # Ends the read transaction, so the login can be noted on the account (SQLite allows one writer and no open readers).
    await session.commit()
    try:
        async with ImapClient(imap_settings, factory) as client:
            yield client
        # end with
    except TimeoutError as e:
        raise HTTPException(status_code=504, detail="The mail server did not answer in time.") from e
    except ImapLoginError as e:
        if e.transient:
            raise HTTPException(status_code=502, detail=f"The mail server failed: {e}") from e
        # end if
        raise HTTPException(status_code=424, detail=f"The mail server rejected the login: {e.server_text}") from e
    except (ImapError, aioimaplib.AioImapException, OSError) as e:
        raise HTTPException(status_code=502, detail=f"The mail server failed: {e}") from e
    # end try
# end def
