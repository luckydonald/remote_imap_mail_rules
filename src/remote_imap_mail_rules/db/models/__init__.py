"""All models; importing this package registers every table on `Base.metadata`."""

from .account import Account
from .git_settings import GitSettings
from .mail_event import EventKind, MailEvent
from .mcp_token import McpToken
from .rule import Rule
from .template import Template
from .user_settings import UserSettings

__all__ = ["Account", "EventKind", "GitSettings", "MailEvent", "McpToken", "Rule", "Template", "UserSettings"]
