"""All models; importing this package registers every table on `Base.metadata`."""

from .account import Account
from .rule import Rule
from .template import Template

__all__ = ["Account", "Rule", "Template"]
