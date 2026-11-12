"""Endpoints of the rule editor, mounted at `/api/editor`."""

from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from pydantic import BaseModel

from .. import rules_file
from ..rules_save import after_rules_saved
from ..rules_store import RulesStore

router = APIRouter()


class EditorConfig(BaseModel):
    mode: Literal["server"] = "server"
    source: Literal["file", "database"]
    file_name: str | None
    exists: bool
    actions_enabled: bool = False


def get_store(request: Request) -> RulesStore:
    store: RulesStore = request.app.state.rules_store
    return store
# end def


@router.get("/config")
async def get_config(request: Request) -> EditorConfig:
    store = get_store(request)
    return EditorConfig(source=store.source, file_name=store.file_name, exists=await store.exists(), actions_enabled=request.app.state.settings.actions_enabled)
# end def


@router.get("/rules")
async def get_rules(request: Request) -> Response:
    text = await get_store(request).read_text()
    if text is None:
        raise HTTPException(status_code=404, detail="There are no rules yet.")
    # end if
    return Response(content=text, media_type="text/plain; charset=utf-8")
# end def


@router.put("/rules", status_code=204)
async def put_rules(request: Request, background: BackgroundTasks) -> None:
    """The body is the raw YAML text, not JSON."""
    try:
        text = (await request.body()).decode("utf-8")
    except UnicodeDecodeError as e:
        raise HTTPException(status_code=422, detail=["The body is not valid UTF-8."]) from e
    # end try
    try:
        await get_store(request).save_text(text)
    except rules_file.InvalidRules as e:
        raise HTTPException(status_code=422, detail=e.messages) from e
    # end try
    background.add_task(after_rules_saved, request.app)
# end def
