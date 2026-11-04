"""Mail browsing, mounted at `/api/mail`. The folder is a query parameter, since folder names contain the delimiter.

Reading is read-only (`EXAMINE`, `BODY.PEEK`). The two write routes (`/flags`, `/move`) only work with `ACTIONS_ENABLED`."""

from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ...imap.client import ImapError
from ...imap.models import FolderCounts
from ..html_sanitize import sanitize_html
from ..imap_session import imap_session
from ..mail_view import DetailOut, FolderOut, PageOut, addresses, attachment_out, detail_fields, folder_out, summary_fields, summary_out
from ..settings import ServerSettings
from .accounts import get_session

router = APIRouter()

MAX_PAGE = 200
USER_FLAGS = {"\\Seen", "\\Flagged", "\\Answered"}  # what the mail view may change
INLINE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp", "application/pdf"}


@router.get("/accounts/{account_id}/folders")
async def list_folders(request: Request, account_id: UUID, session: AsyncSession = Depends(get_session)) -> list[FolderOut]:
    async with imap_session(request, session, account_id) as client:
        folders: list[FolderOut] = []
        for info in await client.list_folders():
            counts: FolderCounts | None = None
            if info.selectable:
                try:
                    counts = await client.folder_counts(info.name)
                except ImapError:
                    counts = None  # a folder that cannot be asked is still shown
                # end try
            # end if
            folders.append(folder_out(info, counts))
        # end for
        return folders
    # end with
# end def


@router.get("/accounts/{account_id}/messages")
async def list_messages(
    request: Request,
    account_id: UUID,
    folder: str = "INBOX",
    before_uid: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=MAX_PAGE),
    session: AsyncSession = Depends(get_session),
) -> PageOut:
    """Newest first. Pass the `next_before_uid` of the previous page to get the next one."""
    async with imap_session(request, session, account_id) as client:
        mails, total = await client.list_page(account_id, folder, limit, before_uid)
    # end with
    last = mails[-1].uid if len(mails) == limit else None
    return PageOut(messages=[summary_out(mail) for mail in mails], total=total, next_before_uid=last)
# end def


@router.get("/accounts/{account_id}/messages/{uid}")
async def get_message(
    request: Request,
    account_id: UUID,
    uid: int,
    folder: str = "INBOX",
    remote_images: bool = False,
    styles: bool = False,
    session: AsyncSession = Depends(get_session),
) -> DetailOut:
    """`remote_images` and `styles` let the HTML load remote images and keep its CSS, both are left out by default."""
    async with imap_session(request, session, account_id) as client:
        mail = await client.fetch_message(account_id, folder, uid)
        if mail is None:
            raise HTTPException(status_code=404, detail="No such message.")
        # end if
        bodies = await mail.load_bodies()
    # end with
    attachments = [attachment_out(account_id, mail, attachment) for attachment in mail.attachments if attachment.part]
    by_content_id = {attachment.content_id.lower(): attachment.url for attachment in attachments if attachment.content_id}
    sanitized = (
        sanitize_html(bodies.html, lambda content_id: by_content_id.get(content_id.lower()), allow_remote=remote_images, allow_styles=styles)
        if bodies.html
        else None
    )
    return DetailOut(
        **summary_fields(mail),  # type: ignore[arg-type]
        **detail_fields(mail),  # type: ignore[arg-type]
        to=addresses(mail, "To"),
        cc=addresses(mail, "Cc"),
        reply_to=addresses(mail, "Reply-To"),
        message_id=str(mail.headers["Message-ID"]) if mail.headers.get("Message-ID") else None,
        text=bodies.text,
        html=sanitized.html if sanitized else None,
        blocked_images=sanitized.blocked_images if sanitized else [],
        broken_embeds=sanitized.broken_embeds if sanitized else [],
        styles_blocked=sanitized.styles_blocked if sanitized else False,
        remote_images_allowed=remote_images,
        styles_allowed=styles,
        attachments=attachments,
    )
# end def


@router.get("/accounts/{account_id}/messages/{uid}/parts/{part}")
async def get_part(
    request: Request, account_id: UUID, uid: int, part: str, folder: str = "INBOX", session: AsyncSession = Depends(get_session)
) -> Response:
    """An attachment or inline image. Anything that a browser could run is forced to download and sandboxed."""
    async with imap_session(request, session, account_id) as client:
        found = await client.fetch_part(folder, uid, part)
    # end with
    if found is None:
        raise HTTPException(status_code=404, detail="No such part.")
    # end if
    info, data = found
    disposition = "inline" if info.mime_type in INLINE_TYPES else "attachment"
    filename = quote(info.filename or f"part-{part}")
    return Response(
        content=data,
        media_type=info.mime_type,
        headers={
            "Content-Disposition": f"{disposition}; filename*=UTF-8''{filename}",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "Cache-Control": "private, max-age=3600",
        },
    )
# end def


class FlagsIn(BaseModel):
    add: list[str] = []
    remove: list[str] = []
# end class


class MoveIn(BaseModel):
    folder: str
# end class


class MoveOut(BaseModel):
    folder: str
    uid: int | None = None
# end class


def require_actions(request: Request) -> None:
    settings: ServerSettings = request.app.state.settings
    if not settings.actions_enabled:
        raise HTTPException(status_code=409, detail="actions_disabled")
    # end if
# end def


@router.post("/accounts/{account_id}/messages/{uid}/flags", status_code=204)
async def post_flags(
    request: Request, account_id: UUID, uid: int, body: FlagsIn, folder: str = "INBOX", session: AsyncSession = Depends(get_session)
) -> Response:
    """Sets or clears `\\Seen`, `\\Flagged` and `\\Answered`, nothing else."""
    require_actions(request)
    unknown = [flag for flag in (*body.add, *body.remove) if flag not in USER_FLAGS]
    if unknown:
        raise HTTPException(status_code=422, detail=f"Flags not allowed: {', '.join(unknown)}")
    # end if
    async with imap_session(request, session, account_id) as client:
        await client.store_flags(folder, uid, add=tuple(body.add), remove=tuple(body.remove))
    # end with
    return Response(status_code=204)
# end def


@router.post("/accounts/{account_id}/messages/{uid}/move")
async def post_move(
    request: Request, account_id: UUID, uid: int, body: MoveIn, folder: str = "INBOX", session: AsyncSession = Depends(get_session)
) -> MoveOut:
    """Moves the mail to another folder of the same account."""
    require_actions(request)
    if body.folder == folder:
        raise HTTPException(status_code=422, detail="The mail is in that folder already.")
    # end if
    async with imap_session(request, session, account_id) as client:
        moved = await client.move(folder, uid, body.folder)
    # end with
    return MoveOut(folder=moved.folder, uid=moved.uid)
# end def
