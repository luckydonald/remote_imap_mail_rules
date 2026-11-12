"""The scopes of an MCP token, `<resource>:<r|w|d>` (read, write, delete). They are independent, write does not imply read."""

from enum import StrEnum


class Scope(StrEnum):
    rules_r = "rules:r"
    rules_w = "rules:w"
    rules_d = "rules:d"
    accounts_r = "accounts:r"
    accounts_w = "accounts:w"
    accounts_d = "accounts:d"
    accounts_password_r = "accounts.password:r"
    accounts_password_w = "accounts.password:w"
    folders_r = "folders:r"
    folders_w = "folders:w"
    """Reserved, no tool creates, moves or renames folders yet."""
    folders_d = "folders:d"
    """Reserved, no tool deletes folders yet."""
    events_r = "events:r"
    events_d = "events:d"
    mails_r = "mails:r"
    """Today only decides whether mail titles and addresses show in events and dry runs."""
    mails_w = "mails:w"
    """Reserved."""
    mails_d = "mails:d"
    """Reserved."""
# end class


PRESETS: dict[str, list[Scope]] = {
    "read_only": [Scope.rules_r, Scope.accounts_r, Scope.folders_r, Scope.events_r],
    "rules_editor": [Scope.rules_r, Scope.rules_w, Scope.rules_d, Scope.accounts_r, Scope.folders_r, Scope.events_r],
    "everything": list(Scope),
}


def resource_of(scope: Scope) -> str:
    return scope.value.rsplit(":", 1)[0]
# end def
