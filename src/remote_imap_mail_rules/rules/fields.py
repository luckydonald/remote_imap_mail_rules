"""Enumerations of the fields and operators a rule condition can use."""

from enum import StrEnum


class TextField(StrEnum):
    """Fields holding one text value or a list of them."""

    account_id = "account_id"
    folder = "folder"
    subject = "subject"
    body_text = "body_text"
    body_html = "body_html"
    message_id = "message_id"
    in_reply_to = "in_reply_to"
    references = "references"
    list_id = "list_id"
    auto_submitted = "auto_submitted"
    precedence = "precedence"
    importance = "importance"
    mime_type = "mime_type"
    keywords = "keywords"
    auth_spf = "auth_spf"
    auth_dkim = "auth_dkim"
    auth_dmarc = "auth_dmarc"
    attachment_mime_type = "attachment_mime_type"
    attachment_filename = "attachment_filename"
    attachment_extension = "attachment_extension"
# end class


class AddressField(StrEnum):
    """Fields holding one or more email addresses."""

    from_ = "from"
    sender = "sender"
    reply_to = "reply_to"
    return_path = "return_path"
    to = "to"
    cc = "cc"
    bcc = "bcc"
    recipients = "recipients"
    delivered_to = "delivered_to"
# end class


class AddressPart(StrEnum):
    """Which part of an address to compare, so rules can match `Max <m@example.com>` at the wanted granularity."""

    full = "full"
    name = "name"
    address = "address"
    local_part = "local_part"
    domain = "domain"
# end class


class NumberField(StrEnum):
    """Numeric fields."""

    size = "size"
    spam_score = "spam_score"
    attachments_count = "attachments_count"
    attachment_size = "attachment_size"
    uid = "uid"
    modseq = "modseq"
# end class


class DateField(StrEnum):
    """Date and time fields."""

    date_sent = "date_sent"
    date_received = "date_received"
# end class


class BoolField(StrEnum):
    """Boolean fields."""

    seen = "seen"
    flagged = "flagged"
    answered = "answered"
    draft = "draft"
    deleted = "deleted"
    spam_flag = "spam_flag"
    is_reply = "is_reply"
    has_list_unsubscribe = "has_list_unsubscribe"
    attachment_inline = "attachment_inline"
# end class


class TextOperator(StrEnum):
    equals = "equals"
    contains = "contains"
    startswith = "startswith"
    endswith = "endswith"
    regex = "regex"
    glob = "glob"
    in_ = "in"
# end class


class CompareOperator(StrEnum):
    eq = "eq"
    ne = "ne"
    lt = "lt"
    gt = "gt"
    gte = "gte"
    lte = "lte"
    between = "between"
# end class


class PresenceOperator(StrEnum):
    exists = "exists"
    empty = "empty"
# end class


class Quantifier(StrEnum):
    """For multi-valued fields: how many of the values need to match."""

    any = "any"
    all = "all"
    none = "none"
# end class
