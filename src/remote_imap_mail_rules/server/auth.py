"""The login session: a Fernet token in a cookie, signed by `SECRET_KEY`. It says "the admin is logged in", and only while the admin login is unchanged."""

import asyncio
import hashlib
import hmac

from cryptography.fernet import InvalidToken
from fastapi import HTTPException, Request
from fastapi.responses import Response

from ..db.crypto import CryptoError, make_fernet
from .settings import ServerSettings

SESSION_COOKIE = "session"
SESSION_SECONDS = 30 * 24 * 3600
FAILED_LOGIN_DELAY = 0.5


def not_configured(settings: ServerSettings) -> str | None:
    """Why nobody can log in, or `None` when the server is set up for it."""
    if settings.secret_key is None:
        return "SECRET_KEY is not set, so nobody can log in."
    # end if
    if not settings.admin_username or settings.admin_password is None or not settings.admin_password.get_secret_value():
        return "ADMIN_USERNAME and ADMIN_PASSWORD are not set, so nobody can log in."
    # end if
    return None
# end def


def admin_fingerprint(settings: ServerSettings) -> bytes:
    """An HMAC of the admin login, so changing the username or the password ends all sessions. Raises `CryptoError` if not configured."""
    if settings.secret_key is None or not settings.admin_username or settings.admin_password is None:
        raise CryptoError(not_configured(settings) or "The admin login is not configured.")
    # end if
    message = settings.admin_username.encode() + b"\0" + settings.admin_password.get_secret_value().encode()
    return hmac.new(settings.secret_key.get_secret_value().encode(), message, hashlib.sha256).hexdigest().encode()
# end def


def check_admin_credentials(settings: ServerSettings, username: str, password: str) -> bool:
    """Compares both fields in constant time, without stopping at the first wrong one."""
    if not_configured(settings) is not None:
        return False
    # end if
    assert settings.admin_username is not None and settings.admin_password is not None
    right_username = hmac.compare_digest(settings.admin_username.encode(), username.encode())
    right_password = hmac.compare_digest(settings.admin_password.get_secret_value().encode(), password.encode())
    return right_username & right_password
# end def


async def failed_login_pause() -> None:
    """A cheap brake on guessing."""
    await asyncio.sleep(FAILED_LOGIN_DELAY)
# end def


def make_session_token(settings: ServerSettings) -> str:
    """Raises `CryptoError` without a usable `SECRET_KEY` or the admin login."""
    return make_fernet(settings.secret_key).encrypt(admin_fingerprint(settings)).decode()
# end def


def is_logged_in(request: Request) -> bool:
    settings: ServerSettings = request.app.state.settings
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return False
    # end if
    try:
        content = make_fernet(settings.secret_key).decrypt(token.encode(), ttl=SESSION_SECONDS)
        return hmac.compare_digest(content, admin_fingerprint(settings))
    except (CryptoError, InvalidToken):
        return False
    # end try
# end def


def require_login(request: Request) -> None:
    """Dependency for every router except `/api/auth`. Without a `SECRET_KEY` or the admin login nobody can log in, which is reported as such."""
    reason = not_configured(request.app.state.settings)
    if reason is not None:
        raise HTTPException(status_code=503, detail=reason)
    # end if
    if not is_logged_in(request):
        raise HTTPException(status_code=401, detail="Not logged in.")
    # end if
# end def


def set_session_cookie(request: Request, response: Response, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE, token, max_age=SESSION_SECONDS, httponly=True, samesite="lax", secure=request.url.scheme == "https", path="/"
    )
# end def


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
# end def
