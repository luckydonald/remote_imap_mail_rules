"""Helpers of the tools: the app they run in, a database session, and the API handlers called as functions."""

import asyncio
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from mcp.server.mcpserver.exceptions import ToolError
from sqlalchemy.ext.asyncio import AsyncSession

from .scopes import Scope
from .tokens import current_caller


def request_of(app: FastAPI) -> Request:
    """A request that only knows its app, enough for the API handlers that read `request.app.state`."""
    return Request({"type": "http", "app": app, "headers": [], "method": "GET", "path": "/", "query_string": b""})
# end def


@asynccontextmanager
async def db_session(app: FastAPI) -> AsyncIterator[AsyncSession]:
    async with app.state.session_factory() as session:
        yield session
        await session.commit()
    # end with
# end def


def detail_text(detail: Any) -> str:
    if isinstance(detail, list):
        return "; ".join(str(item) for item in detail)
    # end if
    return str(detail)
# end def


async def api_call[T](call: Awaitable[T]) -> T:
    """Awaits an API handler and turns its `HTTPException` into a tool error the client can read."""
    try:
        return await call
    except HTTPException as e:
        raise ToolError(detail_text(e.detail)) from e
    # end try
# end def


def has_scope(scope: Scope) -> bool:
    caller = current_caller.get()
    return caller is not None and scope in caller.scopes
# end def


def keep_task(app: FastAPI, task: "asyncio.Task[None]") -> None:
    """Holds a reference to a background task until it is done, so it is not garbage collected."""
    tasks: set[asyncio.Task[None]] = app.state.mcp_tasks
    tasks.add(task)
    task.add_done_callback(tasks.discard)
# end def
