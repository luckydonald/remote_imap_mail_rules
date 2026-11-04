"""Endpoints of the git control of the rules folder, mounted at `/api/git`."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from ..git_repo import GitError
from ..git_service import AuthMethod, GitService, GitState

router = APIRouter()


class GitSettingsUpdate(BaseModel):
    enabled: bool
    auto_commit: bool
    auto_push: bool
    remote_url: str = Field(max_length=1024)
    branch: str = Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9._/-]+$")
    auth_method: AuthMethod
    username: str = Field(max_length=255)
    token: str | None = Field(default=None, description="`None` keeps the stored token, an empty string clears it.")
    author_name: str = Field(min_length=1, max_length=255)
    author_email: str = Field(min_length=1, max_length=255)
# end class


class ActionResult(BaseModel):
    done: bool
    state: GitState
# end class


def get_service(request: Request) -> GitService:
    service: GitService = request.app.state.git
    return service
# end def


@router.get("")
async def get_state(request: Request) -> GitState:
    try:
        return await get_service(request).state()
    except GitError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    # end try
# end def


@router.put("/settings")
async def put_settings(request: Request, update: GitSettingsUpdate) -> GitState:
    service = get_service(request)
    if update.auto_push and not update.auto_commit:
        raise HTTPException(status_code=422, detail="Pushing automatically needs committing automatically.")
    # end if
    if update.remote_url.startswith("-"):
        raise HTTPException(status_code=422, detail="The remote URL must not start with a dash.")
    # end if
    values = update.model_dump(exclude={"token"})
    try:
        await service.update_settings(values, update.token)
        return await service.state()
    except GitError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    # end try
# end def


@router.post("/ssh-key")
async def post_ssh_key(request: Request) -> GitState:
    service = get_service(request)
    service.generate_key()
    return await service.state()
# end def


@router.post("/{action}")
async def post_action(request: Request, action: Literal["init", "commit", "push", "fetch"]) -> ActionResult:
    service = get_service(request)
    try:
        done = await service.run(action)
    except GitError as e:
        # The status carries the message too; the 502 tells the UI the action failed.
        raise HTTPException(status_code=502, detail=str(e)) from e
    # end try
    return ActionResult(done=done, state=await service.state())
# end def
