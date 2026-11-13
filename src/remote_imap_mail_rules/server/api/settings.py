"""The admin's settings, mounted at `/api/settings`. They live in the database, so every browser shows the same."""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import user_settings
from .accounts import get_session

router = APIRouter()


class SettingsOut(BaseModel):
    cache_unread: bool
    cache_opened_unread: bool
    cache_inbox: bool
    cache_inbox_count: int = Field(ge=0, le=100_000)
    cache_max_age_days: int = Field(ge=0, le=36_500)
    #: When the mail view marks a mail read by itself.
    auto_read: Literal["off", "open", "scrolled"]
# end class


@router.get("")
async def get_settings(session: AsyncSession = Depends(get_session)) -> SettingsOut:
    row = await user_settings.get_settings(session)
    return SettingsOut.model_validate(row, from_attributes=True)
# end def


@router.put("")
async def put_settings(update: SettingsOut, session: AsyncSession = Depends(get_session)) -> SettingsOut:
    row = await user_settings.save_settings(session, update.model_dump())
    return SettingsOut.model_validate(row, from_attributes=True)
# end def
