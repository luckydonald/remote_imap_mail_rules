"""The FastAPI application."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from starlette.types import Scope

from ..config import ImapSettings
from ..db import accounts as account_repository
from ..db.engine import create_engine, create_session_factory
from ..db.migrate import upgrade
from ..imap.client import ConnectionFactory, connect_aioimaplib
from ..mcp_server.server import mount_mcp
from .api import accounts, auth, dry_run, editor, events, git, log, mail, mcp_tokens, public, sample_error, settings as settings_api
from .auth import require_login
from .git_repo import GitRepo
from .git_service import GitService
from .login_log import recording_factory
from .rules_store import DatabaseRulesStore, FileRulesStore, RulesStore
from .sentry import report_startup_failure
from .settings import ServerSettings
from .watcher import Watcher


NO_CACHE = {"sw.js", "index.html", "manifest.webmanifest"}


class SpaStaticFiles(StaticFiles):
    """Serves `index.html` for paths without a file, so the frontend router can own the URLs (`/mail/<account>/<folder>`)."""

    async def get_response(self, path: str, scope: Scope):
        try:
            response = await super().get_response(path, scope)
            if path in NO_CACHE:
                response.headers["Cache-Control"] = "no-cache"  # the service worker and the shell must be revalidated to update
            # end if
            return response
        except HTTPException as exception:
            # An unknown `/api` path stays a 404, a missing built asset too; folder names may contain dots, so no check for an extension.
            if exception.status_code != 404 or path.startswith(("api/", "assets/")):
                raise
            # end if
            return await super().get_response("index.html", scope)
        # end try
    # end def
# end class


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
        try:
            await upgrade(settings.database_url)
            if isinstance(store, DatabaseRulesStore):
                await store.write_mirror()
            # end if
            async with session_factory() as session:
                await account_repository.seed_from_env(session, env_account, settings.secret_key)
                await session.commit()
            # end with
        except Exception as e:
            report_startup_failure(e)
            raise
        # end try
        app.state.watcher.start()
        async with mcp_server.session_manager.run():
            yield
        # end with
        await app.state.watcher.stop()
        await engine.dispose()
    # end def

    app = FastAPI(title="remote_imap_mail_rules", lifespan=lifespan)
    app.state.settings = settings
    app.state.session_factory = session_factory
    app.state.env_account = env_account
    app.state.raw_imap_factory = imap_factory
    imap_factory = recording_factory(imap_factory, session_factory)
    app.state.imap_factory = imap_factory
    store: RulesStore = FileRulesStore(settings.rules_path) if settings.rules_path else DatabaseRulesStore(session_factory, settings.git_dir)
    app.state.rules_store = store
    app.state.git = GitService(GitRepo(settings.git_dir, settings.git_state_dir), session_factory, settings.secret_key)
    app.state.watcher = Watcher(session_factory, store, settings.secret_key, imap_factory, enabled=settings.watch_enabled, actions_enabled=settings.actions_enabled)
    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(public.router, prefix="/api/public", tags=["public"])
    # Everything else under `/api` needs the login, set here so that a new router cannot forget it.
    protected = [Depends(require_login)]
    app.include_router(editor.router, prefix="/api/editor", tags=["editor"], dependencies=protected)
    app.include_router(settings_api.router, prefix="/api/settings", tags=["settings"], dependencies=protected)
    app.include_router(mcp_tokens.router, prefix="/api/mcp-tokens", tags=["mcp-tokens"], dependencies=protected)
    app.include_router(git.router, prefix="/api/git", tags=["git"], dependencies=protected)
    app.include_router(accounts.router, prefix="/api/accounts", tags=["accounts"], dependencies=protected)
    app.include_router(mail.router, prefix="/api/mail", tags=["mail"], dependencies=protected)
    app.include_router(dry_run.router, prefix="/api/dry-run", tags=["dry-run"], dependencies=protected)
    app.include_router(sample_error.router, prefix="/api/sample-error", tags=["sample-error"], dependencies=protected)
    app.include_router(events.router, prefix="/api/mail", tags=["mail"], dependencies=protected)
    app.include_router(log.router, prefix="/api/log", tags=["log"], dependencies=protected)
    mcp_server = mount_mcp(app)
    if settings.frontend_dist.is_dir():
        # Mounted last, so `/api` wins; `html=True` serves `index.html` for `/`.
        app.mount("/", SpaStaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
    # end if
    return app
# end def
