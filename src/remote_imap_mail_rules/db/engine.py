"""Engine and session factory. Only the URL decides the backend."""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./db.sqlite3"


def create_engine(database_url: str) -> AsyncEngine:
    return create_async_engine(database_url)
# end def


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
# end def


async def iter_session(factory: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    """Yields one session and commits on success, for use as a FastAPI dependency body."""
    async with factory() as session:
        yield session
        await session.commit()
    # end with
# end def
