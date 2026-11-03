"""Login, logout and session check, mounted at `/api/auth`. Everything else under `/api` needs the session."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...db import accounts as repository
from ...db.crypto import CryptoError
from ..auth import clear_session_cookie, is_logged_in, make_session_token, set_session_cookie
from .accounts import get_session, get_settings, no_key

router = APIRouter()


class LoginIn(BaseModel):
    username: str = Field(min_length=1)
    password: str = Field(min_length=1)


@router.post("/login", status_code=204)
async def login(request: Request, response: Response, body: LoginIn, session: AsyncSession = Depends(get_session)) -> None:
    """Any registered account's username and password unlock the service, it is single user."""
    settings = get_settings(request)
    try:
        token = make_session_token(settings)
    except CryptoError as e:
        raise no_key() from e
    # end try
    account = await repository.find_by_credentials(session, settings.secret_key, body.username, body.password)
    if account is None:
        raise HTTPException(status_code=401, detail="Wrong username or password.")
    # end if
    set_session_cookie(request, response, token)
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
