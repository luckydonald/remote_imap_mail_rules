"""The scopes of an MCP token, `<resource>:<read|write|delete>`. They are independent, write does not imply read."""

from enum import StrEnum


class Scope(StrEnum):
    rules_read = "rules:read"
    rules_write = "rules:write"
    rules_delete = "rules:delete"
    accounts_read = "accounts:read"
    accounts_write = "accounts:write"
    accounts_delete = "accounts:delete"
    accounts_password_read = "accounts.password:read"
    accounts_password_write = "accounts.password:write"
    folders_read = "folders:read"
    folders_write = "folders:write"
    """Reserved, no tool creates, moves or renames folders yet."""
    folders_delete = "folders:delete"
    """Reserved, no tool deletes folders yet."""
    events_read = "events:read"
    events_delete = "events:delete"
    mails_read = "mails:read"
    """Today only decides whether mail titles and addresses show in events and dry runs."""
    mails_write = "mails:write"
    """Reserved."""
    mails_delete = "mails:delete"
    """Reserved."""
# end class


PRESETS: dict[str, list[Scope]] = {
    "read_only": [Scope.rules_read, Scope.accounts_read, Scope.folders_read, Scope.events_read],
    "rules_editor": [Scope.rules_read, Scope.rules_write, Scope.rules_delete, Scope.accounts_read, Scope.folders_read, Scope.events_read],
    "everything": list(Scope),
}


def resource_of(scope: Scope) -> str:
    return scope.value.rsplit(":", 1)[0]
# end def
