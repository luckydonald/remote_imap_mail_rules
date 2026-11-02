"""Notifies about changes of a folder: IMAP `IDLE` push when the server supports it, polling otherwise."""

import asyncio
from collections.abc import AsyncIterator

from aioimaplib import AioImapException

from .client import ImapClient
from .models import ChangeEvent, ChangeKind

IDLE_RENEW_SECONDS = 28 * 60


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
        # end if
    # end try
    return ChangeEvent(kind=ChangeKind.push, folder=folder)
# end def


async def watch(client: ImapClient, folder: str, poll_interval: float, idle_timeout: float = IDLE_RENEW_SECONDS) -> AsyncIterator[ChangeEvent]:
    """Yields an event whenever the folder may have changed: after each server push, or after each `poll_interval` without IDLE.

    The folder must already be examined. Events are only hints, the caller then asks the client what actually changed.
    """
    use_idle = client.has_capability("IDLE")
    while True:
        if not use_idle:
            await asyncio.sleep(poll_interval)
            yield ChangeEvent(kind=ChangeKind.poll, folder=folder)
            continue
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
