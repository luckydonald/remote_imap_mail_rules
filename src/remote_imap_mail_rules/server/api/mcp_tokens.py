"""Management of the MCP tokens, mounted at `/api/mcp-tokens`. Behind the login; the MCP server itself uses the tokens."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import mcp_tokens as repository
from ...db.models import McpToken
from ...db.models.account import as_utc
from ...mcp_server.scopes import PRESETS, Scope
from .accounts import get_session

router = APIRouter()


class TokenOut(BaseModel):
    id: UUID
    name: str
    prefix: str
    scopes: list[str]
    created_at: datetime
    last_used_at: datetime | None
    revoked_at: datetime | None
# end class


class TokenCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    scopes: list[Scope] = Field(min_length=1)
# end class


class TokenCreated(TokenOut):
    token: str
    """The plain token, shown only now."""
# end class


class ScopeList(BaseModel):
    scopes: list[str]
    presets: dict[str, list[str]]
# end class


def to_out(row: McpToken) -> TokenOut:
    return TokenOut(
        id=row.id, name=row.name, prefix=row.prefix, scopes=list(row.scopes), created_at=as_utc(row.created_at),
        last_used_at=None if row.last_used_at is None else as_utc(row.last_used_at),
        revoked_at=None if row.revoked_at is None else as_utc(row.revoked_at),
    )
# end def


@router.get("/scopes")
async def list_scopes() -> ScopeList:
    return ScopeList(scopes=[scope.value for scope in Scope], presets={name: [s.value for s in scopes] for name, scopes in PRESETS.items()})
# end def


@router.get("")
async def list_tokens(session: AsyncSession = Depends(get_session)) -> list[TokenOut]:
    return [to_out(row) for row in await repository.list_tokens(session)]
# end def


@router.post("", status_code=201)
async def create_token(body: TokenCreate, session: AsyncSession = Depends(get_session)) -> TokenCreated:
    row, token = await repository.create_token(session, body.name, [scope.value for scope in body.scopes])
    return TokenCreated(**to_out(row).model_dump(), token=token)
# end def


@router.delete("/{token_id}", status_code=204)
async def revoke_token(token_id: UUID, session: AsyncSession = Depends(get_session)) -> None:
    row = await repository.get_token(session, token_id)
    if row is None:
        raise HTTPException(status_code=404, detail="No such token.")
    # end if
    await repository.revoke_token(session, row)
# end def
