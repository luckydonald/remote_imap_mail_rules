"""Notes every IMAP login on the account row, so a rejected password shows up in the accounts screen."""

import logging
from typing import Any

from aioimaplib import Response
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..config import ImapSettings
from ..db import accounts as repository
from ..imap.client import ConnectionFactory, ImapLoginError
from ..imap.connection import ImapConnection

logger = logging.getLogger(__name__)


class LoginRecorder:
    """Delegates to the connection, but tells `record` how `login` went."""

    def __init__(self, connection: ImapConnection, settings: ImapSettings, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._connection = connection
        self._settings = settings
        self._session_factory = session_factory

    def __getattr__(self, name: str) -> Any:
        return getattr(self._connection, name)
    # end def

    async def login(self, user: str, password: str) -> Response:
        response = await self._connection.login(user, password)
        await self.record(response)
        return response
    # end def

    async def record(self, response: Response) -> None:
        """A failing database must never break a login, and an answer that is not about the credentials (`transient`) is not counted."""
        try:
            if response.result == "OK":
                error = None
            else:
                refusal = ImapLoginError(response)
                if refusal.transient:
                    return
                # end if
                error = refusal.server_text or response.result
            # end if
            async with self._session_factory() as session:
                await repository.record_login(session, self._settings.imap_account_id, error)
                await session.commit()
            # end with
        except Exception:
            logger.exception("Could not note the login of account %s", self._settings.imap_account_id)
        # end try
    # end def
# end class


def recording_factory(factory: ConnectionFactory, session_factory: async_sessionmaker[AsyncSession]) -> ConnectionFactory:
    """Wraps a connection factory; the account is the one in the `ImapSettings` the connection is opened for."""

    def open_connection(settings: ImapSettings) -> ImapConnection:
        return LoginRecorder(factory(settings), settings, session_factory)  # type: ignore[return-value]
    # end def

    return open_connection
# end def
