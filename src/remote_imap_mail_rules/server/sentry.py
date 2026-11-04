"""Error reporting to Sentry or Bugsink. Everything here does nothing while `SENTRY_DSN` is empty."""

import logging
import subprocess

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.starlette import StarletteIntegration

from .settings import ServerSettings

logger = logging.getLogger(__name__)

UNKNOWN = "unknown"


def git_output(*args: str) -> str:
    """Output of a git command, empty without git or a checkout (the Docker image has neither)."""
    try:
        return subprocess.run(["git", *args], capture_output=True, text=True, check=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""
    # end try
# end def


def commit_of(settings: ServerSettings) -> str:
    """`SOURCE_COMMIT` (Coolify), else the local checkout, else `unknown`."""
    return settings.source_commit or git_output("rev-parse", "HEAD") or UNKNOWN
# end def


def release_of(settings: ServerSettings) -> str:
    """The commit unless `SENTRY_RELEASE` names one, so every deploy is its own release without a version to bump."""
    return settings.sentry_release or commit_of(settings)
# end def


def frontend_release_of(settings: ServerSettings) -> str:
    """The browser reports under the release of the server that served it, unless told otherwise."""
    return settings.vite_sentry_release or release_of(settings)
# end def


def frontend_environment_of(settings: ServerSettings) -> str:
    return settings.vite_sentry_environment or settings.sentry_environment
# end def


def init_sentry(settings: ServerSettings) -> bool:
    """Call before the app is created, so errors while it is set up are reported too. Returns whether reporting is on."""
    if not settings.sentry_dsn:
        return False
    # end if
    commit = commit_of(settings)
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.sentry_environment or None,
        release=release_of(settings),
        integrations=[FastApiIntegration(), StarletteIntegration()],
        send_default_pii=False,
        traces_sample_rate=settings.sentry_traces_sample_rate,
    )
    sentry_sdk.set_tag("git_commit", commit)
    logger.info("Error reporting is on (release %s).", release_of(settings))
    return True
# end def


def report_startup_failure(error: BaseException) -> None:
    """The ASGI lifespan is not instrumented, so a failing migration would never show up otherwise. Flushes, the process is about to exit."""
    sentry_sdk.capture_exception(error)
    sentry_sdk.flush(timeout=5)
# end def
