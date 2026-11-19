"""Endpoints that need no login, mounted at `/api/public`: the health check and what the browser needs before anyone logged in."""

from fastapi import APIRouter, Request
from pydantic import BaseModel

from ..sentry import frontend_environment_of, frontend_release_of
from ..settings import ServerSettings

router = APIRouter()


class SentryClientConfig(BaseModel):
    dsn: str
    environment: str | None
    release: str
    traces_sample_rate: float
# end class


class TodoOverlayClientConfig(BaseModel):
    url: str | None
    token: str | None
# end class


class ClientConfig(BaseModel):
    sentry: SentryClientConfig | None
    todo_overlay: TodoOverlayClientConfig | None
# end class


class Health(BaseModel):
    status: str = "ok"
# end class


@router.get("/health")
async def health() -> Health:
    """For the container health check; it touches neither the database nor IMAP, so a slow mailbox cannot get the container restarted."""
    return Health()
# end def


@router.get("/client-config")
async def client_config(request: Request) -> ClientConfig:
    """Public settings for the browser, read at runtime so one image serves every deployment."""
    settings: ServerSettings = request.app.state.settings
    return ClientConfig(
        sentry=SentryClientConfig(
            dsn=settings.vite_sentry_dsn,
            environment=frontend_environment_of(settings) or None,
            release=frontend_release_of(settings),
            traces_sample_rate=settings.vite_sentry_traces_sample_rate,
        ) if settings.vite_sentry_dsn else None,
        todo_overlay=TodoOverlayClientConfig(
            url=settings.sync_todo_url or None,
            token=settings.sync_todo_token or None,
        ) if settings.sync_todo_overlay_enable else None,
    )
# end def
