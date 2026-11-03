"""The login session: a Fernet token in a cookie, signed by `SECRET_KEY`. It only says "logged in", it carries no account."""

from cryptography.fernet import InvalidToken
from fastapi import HTTPException, Request
from fastapi.responses import Response

from ..db.crypto import CryptoError, make_fernet
from .settings import ServerSettings

SESSION_COOKIE = "session"
SESSION_SECONDS = 30 * 24 * 3600
TOKEN_CONTENT = b"logged-in"


def make_session_token(settings: ServerSettings) -> str:
    """Raises `CryptoError` without a usable `SECRET_KEY`."""
    return make_fernet(settings.secret_key).encrypt(TOKEN_CONTENT).decode()
# end def


def is_logged_in(request: Request) -> bool:
    settings: ServerSettings = request.app.state.settings
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return False
    # end if
    try:
        return make_fernet(settings.secret_key).decrypt(token.encode(), ttl=SESSION_SECONDS) == TOKEN_CONTENT
    except (CryptoError, InvalidToken):
        return False
    # end try
# end def


def require_login(request: Request) -> None:
    """Dependency for every router except `/api/auth`. Without a `SECRET_KEY` nobody can log in, which is reported as such."""
    settings: ServerSettings = request.app.state.settings
    if settings.secret_key is None:
        raise HTTPException(status_code=503, detail="SECRET_KEY is not set, so nobody can log in.")
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
