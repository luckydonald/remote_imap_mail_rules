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


class ClientConfig(BaseModel):
    sentry: SentryClientConfig | None


class Health(BaseModel):
    status: str = "ok"


@router.get("/health")
async def health() -> Health:
    """For the container health check; it touches neither the database nor IMAP, so a slow mailbox cannot get the container restarted."""
    return Health()
# end def


@router.get("/client-config")
async def client_config(request: Request) -> ClientConfig:
    """The frontend DSN is public by design (it ends up in every browser), and read at runtime so one image serves every deployment.

    Reporting is off (`sentry` is `null`) without `VITE_SENTRY_DSN`.
    """
    settings: ServerSettings = request.app.state.settings
    if not settings.vite_sentry_dsn:
        return ClientConfig(sentry=None)
    # end if
    return ClientConfig(
        sentry=SentryClientConfig(
            dsn=settings.vite_sentry_dsn,
            environment=frontend_environment_of(settings) or None,
            release=frontend_release_of(settings),
            traces_sample_rate=settings.vite_sentry_traces_sample_rate,
        )
    )
# end def
