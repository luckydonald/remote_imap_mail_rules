"""The JSON shape of folders and mails for the mail browser."""

from datetime import datetime
from email.utils import getaddresses, parseaddr
from urllib.parse import quote

from pydantic import BaseModel

from ..imap.models import FolderCounts, FolderInfo
from ..imap.utf7 import decode_folder_name
from ..mail import Attachment, Mail
from ..rules.extract import SYSTEM_FLAGS, date_value
from ..rules.fields import DateField


class FolderOut(BaseModel):
    name: str
    display_name: str
    delimiter: str | None
    special_use: str | None
    selectable: bool
    messages: int | None = None
    unseen: int | None = None


class AddressOut(BaseModel):
    name: str
    address: str


class SummaryOut(BaseModel):
    uid: int
    sender: AddressOut
    subject: str
    date: datetime | None
    seen: bool
    flagged: bool
    answered: bool
    has_attachments: bool
    size: int | None


class AttachmentOut(BaseModel):
    part: str
    filename: str | None
    mime_type: str
    size: int | None
    inline: bool
    content_id: str | None
    extension: str | None
    url: str


class HeaderOut(BaseModel):
    name: str
    value: str


class DetailOut(SummaryOut):
    to: list[AddressOut]
    cc: list[AddressOut]
    bcc: list[AddressOut]
    reply_to: list[AddressOut]
    sender_header: list[AddressOut]
    return_path: list[AddressOut]
    delivered_to: list[AddressOut]
    headers: list[HeaderOut]
    flags: list[str]
    keywords: list[str]
    date_sent: datetime | None
    mime_type: str | None
    modseq: int | None
    message_id: str | None
    text: str | None
    html: str | None
    attachments: list[AttachmentOut]


class PageOut(BaseModel):
    messages: list[SummaryOut]
    total: int
    next_before_uid: int | None


def folder_out(info: FolderInfo, counts: FolderCounts | None) -> FolderOut:
    return FolderOut(
        name=info.name,
        display_name=decode_folder_name(info.name),
        delimiter=info.delimiter,
        special_use=info.special_use,
        selectable=info.selectable,
        messages=counts.messages if counts else None,
        unseen=counts.unseen if counts else None,
    )
# end def


def addresses(mail: Mail, header: str) -> list[AddressOut]:
    values = [str(value) for value in mail.headers.get_all(header, [])]
    return [AddressOut(name=name, address=address) for name, address in getaddresses(values) if address or name]
# end def


def detail_fields(mail: Mail) -> dict[str, object]:
    """What the rule editor needs to fill conditions: every header and the flags, besides the addresses."""
    return dict(
        bcc=addresses(mail, "Bcc"),
        sender_header=addresses(mail, "Sender"),
        return_path=addresses(mail, "Return-Path"),
        delivered_to=addresses(mail, "Delivered-To"),
        headers=[HeaderOut(name=name, value=str(value)) for name, value in mail.headers.items()],
        flags=sorted(mail.flags),
        keywords=sorted(flag for flag in mail.flags if flag.lower() not in SYSTEM_FLAGS),
        date_sent=date_value(mail, DateField.date_sent),
        mime_type=mail.mime_type,
        modseq=mail.modseq,
    )
# end def


def summary_fields(mail: Mail) -> dict[str, object]:
    name, address = parseaddr(str(mail.headers.get("From", "")))
    return dict(
        uid=mail.uid,
        sender=AddressOut(name=name, address=address),
        subject=str(mail.headers.get("Subject", "")),
        date=mail.date_received,
        seen=mail.has_flag("\\Seen"),
        flagged=mail.has_flag("\\Flagged"),
        answered=mail.has_flag("\\Answered"),
        has_attachments=any(not attachment.inline for attachment in mail.attachments),
        size=mail.size,
    )
# end def


def summary_out(mail: Mail) -> SummaryOut:
    return SummaryOut(**summary_fields(mail))  # type: ignore[arg-type]
# end def


def part_url(account_id: object, folder: str, uid: int, part: str) -> str:
    return f"/api/mail/accounts/{account_id}/messages/{uid}/parts/{part}?folder={quote(folder, safe='')}"
# end def


def attachment_out(account_id: object, mail: Mail, attachment: Attachment) -> AttachmentOut:
    assert attachment.part is not None
    return AttachmentOut(
        part=attachment.part,
        filename=attachment.filename,
        mime_type=attachment.mime_type,
        size=attachment.size,
        inline=attachment.inline,
        content_id=attachment.content_id,
        extension=attachment.extension,
        url=part_url(account_id, mail.folder, mail.uid, attachment.part),
    )
# end def
