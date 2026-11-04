"""Login, logout and session check, mounted at `/api/auth`. Everything else under `/api` needs the session."""

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..auth import (
    check_admin_credentials,
    clear_session_cookie,
    failed_login_pause,
    is_logged_in,
    make_session_token,
    not_configured,
    set_session_cookie,
)
from .accounts import get_settings

router = APIRouter()


class LoginIn(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


@router.post("/login", status_code=204)
async def login(request: Request, response: Response, body: LoginIn) -> None:
    """Only the admin from `ADMIN_USERNAME` and `ADMIN_PASSWORD` can log in, the mail accounts' credentials do not count."""
    settings = get_settings(request)
    reason = not_configured(settings)
    if reason is not None:
        raise HTTPException(status_code=503, detail=reason)
    # end if
    if not check_admin_credentials(settings, body.username, body.password):
        await failed_login_pause()
        raise HTTPException(status_code=401, detail="Wrong username or password.")
    # end if
    set_session_cookie(request, response, make_session_token(settings))
# end def


@router.post("/logout", status_code=204)
async def logout(response: Response) -> None:
    clear_session_cookie(response)
# end def


@router.get("/me", status_code=204)
async def me(request: Request) -> None:
    if not is_logged_in(request):
        raise HTTPException(status_code=401, detail="Not logged in.")
    # end if
# end def
