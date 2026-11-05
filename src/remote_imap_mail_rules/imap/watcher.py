"""Notifies about changes of a folder: IMAP `IDLE` push when the server supports it, polling otherwise."""

import asyncio
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime, timedelta

from aioimaplib import AioImapException

from .client import ImapClient
from .connection import ImapConnection
from .models import ChangeEvent, ChangeKind

IDLE_RENEW_SECONDS = 28 * 60
IDLE_DONE_WAIT_SECONDS = 5.0


async def _wait_idle_ended(connection: ImapConnection) -> None:
    """Waits for the tagged reply to `IDLE` after `DONE`, so nobody sends a second `DONE` (the server would answer `BAD`).

    Shielded, so it also finishes when the watcher task is cancelled (rules saved) while leaving `IDLE`.
    """

    async def poll() -> None:
        while connection.has_pending_idle():
            await asyncio.sleep(0.01)
        # end while
    # end def

    try:
        await asyncio.shield(asyncio.wait_for(poll(), timeout=IDLE_DONE_WAIT_SECONDS))
    except (TimeoutError, asyncio.CancelledError):
        pass
    # end try
# end def


async def idle_once(client: ImapClient, folder: str, timeout: float) -> ChangeEvent | None:
    """Waits in `IDLE` until the server pushes something. `None` if the wait timed out, so the caller re-issues `IDLE`."""
    connection = client.conn
    await connection.idle_start(timeout=timeout)
    try:
        await connection.wait_server_push(timeout=timeout)
    except TimeoutError:
        return None
    except asyncio.CancelledError:
        raise
    finally:
        if connection.has_pending_idle():
            connection.idle_done()
            await _wait_idle_ended(connection)
        # end if
    # end try
    return ChangeEvent(kind=ChangeKind.push, folder=folder)
# end def


async def watch(
    client: ImapClient, folder: str, poll_interval: float, idle_timeout: float = IDLE_RENEW_SECONDS,
    on_schedule: Callable[[datetime | None], None] | None = None,
) -> AsyncIterator[ChangeEvent]:
    """Yields an event whenever the folder may have changed: after each server push, or after each `poll_interval` without IDLE.

    The folder must already be examined. Events are only hints, the caller then asks the client what actually changed.
    `on_schedule` is told when the next poll is due before the wait starts, or `None` before waiting in `IDLE` (a push has no planned time).
    """
    use_idle = client.has_capability("IDLE")
    while True:
        if not use_idle:
            if on_schedule is not None:
                on_schedule(datetime.now(UTC) + timedelta(seconds=poll_interval))
            # end if
            await asyncio.sleep(poll_interval)
            yield ChangeEvent(kind=ChangeKind.poll, folder=folder)
            continue
        # end if
        if on_schedule is not None:
            on_schedule(None)
        # end if
        try:
            event = await idle_once(client, folder, idle_timeout)
        except AioImapException:
            use_idle = False
            continue
        # end try
        if event is None:
            continue
        # end if
        yield event
    # end while
# end def
