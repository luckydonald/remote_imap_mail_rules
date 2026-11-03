"""Endpoints of the rule editor, mounted at `/api/editor`."""

from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel

from .. import rules_file
from ..settings import ServerSettings

router = APIRouter()


class EditorConfig(BaseModel):
    mode: Literal["server"] = "server"
    file_name: str
    exists: bool


def get_settings(request: Request) -> ServerSettings:
    settings: ServerSettings = request.app.state.settings
    return settings
# end def


@router.get("/config")
async def get_config(request: Request) -> EditorConfig:
    path = get_settings(request).rules_path
    return EditorConfig(file_name=path.name, exists=path.is_file())
# end def


@router.get("/rules")
async def get_rules(request: Request) -> Response:
    text = await rules_file.read_text(get_settings(request).rules_path)
    if text is None:
        raise HTTPException(status_code=404, detail="The rules file does not exist yet.")
    # end if
    return Response(content=text, media_type="text/plain; charset=utf-8")
# end def


@router.put("/rules", status_code=204)
async def put_rules(request: Request) -> None:
    """The body is the raw YAML text, not JSON."""
    try:
        text = (await request.body()).decode("utf-8")
    except UnicodeDecodeError as e:
        raise HTTPException(status_code=422, detail=["The body is not valid UTF-8."]) from e
    # end try
    try:
        await rules_file.save_text(get_settings(request).rules_path, text)
    except rules_file.InvalidRules as e:
        raise HTTPException(status_code=422, detail=e.messages) from e
    # end try
# end def
