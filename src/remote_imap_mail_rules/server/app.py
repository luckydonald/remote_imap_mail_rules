"""The FastAPI application."""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .api import editor
from .settings import ServerSettings


def create_app(settings: ServerSettings | None = None) -> FastAPI:
    settings = settings or ServerSettings()
    app = FastAPI(title="remote_imap_mail_rules")
    app.state.settings = settings
    app.include_router(editor.router, prefix="/api/editor", tags=["editor"])
    if settings.frontend_dist.is_dir():
        # Mounted last, so `/api` wins; `html=True` serves `index.html` for `/`.
        app.mount("/", StaticFiles(directory=settings.frontend_dist, html=True), name="frontend")
    # end if
    return app
# end def
