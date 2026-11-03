"""The FastAPI application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles

from ..config import ImapSettings
from ..db import accounts as account_repository
from ..db.engine import create_engine, create_session_factory
from ..db.migrate import upgrade
from ..imap.client import ConnectionFactory, connect_aioimaplib
from .api import accounts, auth, editor, mail
from .auth import require_login
from .rules_store import DatabaseRulesStore, FileRulesStore, RulesStore
from .settings import ServerSettings


def create_app(
    settings: ServerSettings | None = None, env_account: ImapSettings | None = None, imap_factory: ConnectionFactory = connect_aioimaplib
) -> FastAPI:
    """`env_account` is the account from the environment, seeded into the database at start-up; `None` seeds nothing.

    `imap_factory` opens the IMAP connections of the mail browser, tests pass a fake.
    """
    settings = settings or ServerSettings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        await upgrade(settings.database_url)
        async with session_factory() as session:
            await account_repository.seed_from_env(session, env_account, settings.secret_key)
            await session.commit()
        # end with
        yield
        await engine.dispose()
    # end def

    app = FastAPI(title="remote_imap_mail_rules", lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.env_account = env_account
    app.state.imap_factory = imap_factory
    store: RulesStore = FileRulesStore(settings.rules_path) if settings.rules_path else DatabaseRulesStore(session_factory)
    app.state.rules_store = store
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    # Everything else under `/api` needs the login, set here so that a new router cannot forget it.
    protected = [Depends(require_login)]
    app.include_router(editor.router, prefix="/api/editor", tags=["editor"], dependencies=protected)
    app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"], dependencies=protected)
    app.include_router(mail.router, prefix="/api/mail", tags=["mail"], dependencies=protected)
    if settings.frontend_dist.is_dir():
        # Mounted last, so `/api` wins; `html=True` serves `index.html` for `/`.
        app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
    # end if
    return app
# end def
