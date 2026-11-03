"""Read-only mail browsing, mounted at `/api/mail`. The folder is a query parameter, since folder names contain the delimiter."""

from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from ...imap.client import ImapError
from ...imap.models import FolderCounts
from ..html_sanitize import sanitize_html
from ..imap_session import imap_session
from ..mail_view import DetailOut, FolderOut, PageOut, addresses, attachment_out, folder_out, summary_fields, summary_out
from .accounts import get_session

router = APIRouter()

MAX_PAGE = 200
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
async def get_message(request: Request, account_id: UUID, uid: int, folder: str = "INBOX", session: AsyncSession = Depends(get_session)) -> DetailOut:
    async with imap_session(request, session, account_id) as client:
        mail = await client.fetch_message(account_id, folder, uid)
        if mail is None:
            raise HTTPException(status_code=404, detail="No such message.")
        # end if
        bodies = await mail.load_bodies()
    # end with
    attachments = [attachment_out(account_id, mail, attachment) for attachment in mail.attachments if attachment.part]
    by_content_id = {attachment.content_id: attachment.url for attachment in attachments if attachment.content_id}
    html = sanitize_html(bodies.html, by_content_id.get) if bodies.html else None
    return DetailOut(
        **summary_fields(mail),  # type: ignore[arg-type]
        to=addresses(mail, "To"),
        cc=addresses(mail, "Cc"),
        reply_to=addresses(mail, "Reply-To"),
        message_id=str(mail.headers["Message-ID"]) if mail.headers.get("Message-ID") else None,
        text=bodies.text,
        html=html,
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
