"""Bearer token check of the `/mcp` endpoint, and the scopes of the token that is calling."""

import json
from collections.abc import Callable
from contextvars import ContextVar
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.types import ASGIApp, Receive, Scope as AsgiScope, Send

from ..db import mcp_tokens
from ..server.auth import not_configured
from ..server.settings import ServerSettings
from .scopes import Scope


StateGetter = Callable[[], tuple[ServerSettings, async_sessionmaker[AsyncSession]]]


@dataclass(frozen=True)
class Caller:
    token_id: str
    name: str
    scopes: frozenset[Scope]
# end class


current_caller: ContextVar[Caller | None] = ContextVar("current_caller", default=None)


def parse_scopes(values: list[str]) -> frozenset[Scope]:
    """Unknown names (from a newer or older version) are ignored."""
    known = {scope.value: scope for scope in Scope}
    return frozenset(known[value] for value in values if value in known)
# end def


async def respond(send: Send, status: int, message: str, headers: list[tuple[bytes, bytes]] | None = None) -> None:
    body = json.dumps({"detail": message}).encode()
    await send({"type": "http.response.start", "status": status, "headers": [(b"content-type", b"application/json"), *(headers or [])]})
    await send({"type": "http.response.body", "body": body})
# end def


class TokenAuthMiddleware:
    """Lets a request through only with a valid, not revoked `Authorization: Bearer <token>`; the caller is then in `current_caller`."""

    def __init__(self, app: ASGIApp, get_state: StateGetter) -> None:
        self.app = app
        self.get_state = get_state
    # end def

    async def __call__(self, scope: AsgiScope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        # end if
        settings, session_factory = self.get_state()
        reason = not_configured(settings)
        if reason is not None:
            await respond(send, 503, reason)
            return
        # end if
        header = dict(scope["headers"]).get(b"authorization", b"").decode()
        scheme, _, token = header.partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            await respond(send, 401, "A bearer token is needed.", [(b"www-authenticate", b"Bearer")])
            return
        # end if
        async with session_factory() as session:
            row = await mcp_tokens.find_active(session, token.strip())
            await session.commit()
            caller = None if row is None else Caller(str(row.id), row.name, parse_scopes(list(row.scopes)))
        # end with
        if caller is None:
            await respond(send, 401, "The token is not valid.", [(b"www-authenticate", b'Bearer error="invalid_token"')])
            return
        # end if
        reset = current_caller.set(caller)
        try:
            await self.app(scope, receive, send)
        finally:
            current_caller.reset(reset)
        # end try
    # end def
# end class
