"""All models; importing this package registers every table on `Base.metadata`."""

from .account import Account
from .mail_event import EventKind, MailEvent
from .rule import Rule
from .template import Template

__all__ = ["Account", "EventKind", "MailEvent", "Rule", "Template"]
