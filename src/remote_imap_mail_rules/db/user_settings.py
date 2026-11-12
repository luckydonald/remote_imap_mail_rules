"""Repository of the single user settings row."""

from sqlalchemy.ext.asyncio import AsyncSession

from .models import UserSettings
from .models.user_settings import ROW_ID


async def get_settings(session: AsyncSession) -> UserSettings:
    """The row, or a transient one with the defaults when nothing was saved yet."""
    row = await session.get(UserSettings, ROW_ID)
    if row is None:
        row = UserSettings(id=ROW_ID, cache_unread=True, cache_opened_unread=True, cache_inbox=True, cache_inbox_count=200, cache_max_age_days=30)
    # end if
    return row
# end def


async def save_settings(session: AsyncSession, values: dict[str, object]) -> UserSettings:
    row = await session.get(UserSettings, ROW_ID)
    if row is None:
        row = await get_settings(session)
        session.add(row)
    # end if
    for key, value in values.items():
        setattr(row, key, value)
    # end for
    await session.flush()
    return row
# end def
