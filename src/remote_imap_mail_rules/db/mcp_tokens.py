"""Repository of the MCP tokens. The plain token exists only in the answer of `create_token`."""

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import McpToken

TOKEN_PREFIX = "rimr_"
LAST_USED_INTERVAL = timedelta(minutes=5)
"""`last_used_at` is written at most this often, so a busy client does not write on every call."""


def hash_token(token: str) -> str:
    """Tokens are long and random, so a plain SHA-256 is enough and allows a lookup by hash."""
    return hashlib.sha256(token.encode()).hexdigest()
# end def


async def create_token(session: AsyncSession, name: str, scopes: list[str]) -> tuple[McpToken, str]:
    token = TOKEN_PREFIX + secrets.token_urlsafe(32)
    row = McpToken(name=name, token_hash=hash_token(token), prefix=token[:8], scopes=sorted(set(scopes)))
    session.add(row)
    await session.flush()
    return row, token
# end def


async def list_tokens(session: AsyncSession) -> list[McpToken]:
    return list((await session.scalars(select(McpToken).order_by(McpToken.created_at.desc()))).all())
# end def


async def get_token(session: AsyncSession, token_id: UUID) -> McpToken | None:
    return await session.get(McpToken, token_id)
# end def


async def find_active(session: AsyncSession, token: str) -> McpToken | None:
    """The row of a token that exists and is not revoked; notes the use."""
    row = await session.scalar(select(McpToken).where(McpToken.token_hash == hash_token(token)))
    if row is None or row.revoked_at is not None:
        return None
    # end if
    now = datetime.now(UTC)
    last = row.last_used_at
    if last is not None and last.tzinfo is None:
        last = last.replace(tzinfo=UTC)
    # end if
    if last is None or now - last >= LAST_USED_INTERVAL:
        row.last_used_at = now
        await session.flush()
    # end if
    return row
# end def


async def revoke_token(session: AsyncSession, row: McpToken) -> None:
    row.revoked_at = datetime.now(UTC)
    await session.flush()
# end def
