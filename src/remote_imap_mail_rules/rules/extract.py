"""Maps rule fields to the values found in a mail. `None` means the field is missing, which makes a condition false."""

import re
from datetime import datetime
from email.utils import getaddresses, parsedate_to_datetime

from ..mail import Mail
from .fields import AddressField, AddressPart, BoolField, DateField, NumberField, TextField

SPAM_SCORE_HEADERS = ("X-Spam-Score", "X-Rspamd-Score", "X-Spam-Status", "X-Spam-Level")
SYSTEM_FLAGS = {"\\seen", "\\answered", "\\flagged", "\\deleted", "\\draft", "\\recent"}
NUMBER = r"-?\d+(?:\.\d+)?"


def header_values(mail: Mail, name: str) -> list[str] | None:
    values = mail.headers.get_all(name)
    if not values:
        return None
    # end if
    return [str(value) for value in values]
# end def


def first_header(mail: Mail, name: str) -> str | None:
    values = header_values(mail, name)
    return values[0] if values else None
# end def


def split_address(name: str, address: str, part: AddressPart) -> str | None:
    local, _, domain = address.rpartition("@")
    match part:
        case AddressPart.full:
            return f"{name} <{address}>" if name else address
        case AddressPart.name:
            return name or None
        case AddressPart.address:
            return address or None
        case AddressPart.local_part:
            return local or None
        case AddressPart.domain:
            return domain or None
    # end match
    return None
# end def


def address_values(mail: Mail, field: AddressField, part: AddressPart) -> list[str] | None:
    names = {
        AddressField.recipients: ["To", "Cc", "Bcc"],
        AddressField.from_: ["From"],
        AddressField.reply_to: ["Reply-To"],
        AddressField.return_path: ["Return-Path"],
        AddressField.delivered_to: ["Delivered-To"],
    }.get(field, [field.value.capitalize()])
    raw: list[str] = []
    for name in names:
        raw.extend(header_values(mail, name) or [])
    # end for
    pairs = [pair for pair in getaddresses(raw) if pair[1]]
    values = [value for name, address in pairs if (value := split_address(name, address, part)) is not None]
    return values or None
# end def


def spam_score(mail: Mail) -> float | None:
    for name in SPAM_SCORE_HEADERS:
        value = first_header(mail, name)
        if value is None:
            continue
        # end if
        if name == "X-Spam-Level":
            stars = value.strip()
            if stars and set(stars) == {"*"}:
                return float(len(stars))
            # end if
            continue
        # end if
        match = re.search(rf"score=({NUMBER})", value) if name == "X-Spam-Status" else re.match(rf"\s*({NUMBER})", value)
        if match:
            return float(match.group(1))
        # end if
    # end for
    return None
# end def


def spam_flag(mail: Mail) -> bool | None:
    flag = first_header(mail, "X-Spam-Flag")
    if flag is not None:
        return flag.strip().lower() in {"yes", "true", "1"}
    # end if
    status = first_header(mail, "X-Spam-Status")
    if status is None:
        return None
    # end if
    return status.strip().lower().startswith("yes")
# end def


def auth_result(mail: Mail, method: str) -> list[str] | None:
    values = header_values(mail, "Authentication-Results")
    if values is None:
        return None
    # end if
    results = [match.group(1).lower() for value in values for match in re.finditer(rf"\b{method}=(\w+)", value)]
    return results or None
# end def


def text_values(mail: Mail, field: TextField, bodies_text: str | None, bodies_html: str | None) -> list[str] | None:
    """Text values of a field; the body parts are passed in because loading them is async."""
    match field:
        case TextField.account_id:
            return [str(mail.account_id)]
        case TextField.folder:
            return [mail.folder]
        case TextField.body_text:
            return [bodies_text] if bodies_text is not None else None
        case TextField.body_html:
            return [bodies_html] if bodies_html is not None else None
        case TextField.mime_type:
            return [mail.mime_type] if mail.mime_type else None
        case TextField.keywords:
            keywords = [flag for flag in mail.flags if flag.lower() not in SYSTEM_FLAGS]
            return keywords or None
        case TextField.attachment_mime_type:
            return [item.mime_type for item in mail.attachments] or None
        case TextField.attachment_filename:
            return [item.filename for item in mail.attachments if item.filename] or None
        case TextField.attachment_extension:
            return [item.extension for item in mail.attachments if item.extension] or None
        case TextField.auth_spf:
            return auth_result(mail, "spf")
        case TextField.auth_dkim:
            return auth_result(mail, "dkim")
        case TextField.auth_dmarc:
            return auth_result(mail, "dmarc")
        case TextField.subject:
            return header_values(mail, "Subject")
        case TextField.message_id:
            return header_values(mail, "Message-ID")
        case TextField.in_reply_to:
            return header_values(mail, "In-Reply-To")
        case TextField.references:
            return header_values(mail, "References")
        case TextField.list_id:
            return header_values(mail, "List-Id")
        case TextField.auto_submitted:
            return header_values(mail, "Auto-Submitted")
        case TextField.precedence:
            return header_values(mail, "Precedence")
        case TextField.importance:
            return header_values(mail, "Importance")
    # end match
    return None
# end def


def number_values(mail: Mail, field: NumberField) -> list[float] | None:
    match field:
        case NumberField.size:
            return [float(mail.size)] if mail.size is not None else None
        case NumberField.uid:
            return [float(mail.uid)]
        case NumberField.modseq:
            return [float(mail.modseq)] if mail.modseq is not None else None
        case NumberField.attachments_count:
            return [float(len(mail.attachments))]
        case NumberField.attachment_size:
            return [float(item.size) for item in mail.attachments if item.size is not None] or None
        case NumberField.spam_score:
            score = spam_score(mail)
            return [score] if score is not None else None
    # end match
    return None
# end def


def date_value(mail: Mail, field: DateField) -> datetime | None:
    if field == DateField.date_received:
        return mail.date_received
    # end if
    raw = first_header(mail, "Date")
    if raw is None:
        return None
    # end if
    try:
        return parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    # end try
# end def


def bool_values(mail: Mail, field: BoolField) -> list[bool] | None:
    flags = {
        BoolField.seen: "\\Seen",
        BoolField.flagged: "\\Flagged",
        BoolField.answered: "\\Answered",
        BoolField.draft: "\\Draft",
        BoolField.deleted: "\\Deleted",
    }
    if field in flags:
        return [mail.has_flag(flags[field])]
    # end if
    match field:
        case BoolField.spam_flag:
            flag = spam_flag(mail)
            return [flag] if flag is not None else None
        case BoolField.is_reply:
            return [bool(first_header(mail, "In-Reply-To") or first_header(mail, "References"))]
        case BoolField.has_list_unsubscribe:
            return [first_header(mail, "List-Unsubscribe") is not None]
        case BoolField.attachment_inline:
            return [item.inline for item in mail.attachments] or None
    # end match
    return None
# end def
