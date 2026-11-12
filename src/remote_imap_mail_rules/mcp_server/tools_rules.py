"""Tools for the rules and templates: whole-file YAML and small structured edits that keep comments and anchors."""

import asyncio
import json
from collections.abc import Callable
from typing import Any

from fastapi import FastAPI
from mcp.server.mcpserver.exceptions import ToolError

from ..rules.schema import schema_text
from ..server import rules_file
from ..server.api import dry_run as dry_run_api
from ..server.rules_save import after_rules_saved
from ..server.rules_store import RulesStore
from .context import api_call, db_session, has_scope, keep_task, request_of
from .redact import mask_sender, redact
from .rule_document import EditError, RuleDocument, plain
from .scoped import ScopedServer
from .scopes import Scope

Condition = dict[str, Any]
ConditionPath = list[int]


async def read_document(app: FastAPI) -> RuleDocument:
    store: RulesStore = app.state.rules_store
    try:
        return RuleDocument(await store.read_text())
    except EditError as e:
        raise ToolError(e.message) from e
    # end try
# end def


async def save_text(app: FastAPI, text: str) -> None:
    """Validates, stores and tells the watcher and git, like the editor's save. Raises a `ToolError` with the messages when invalid."""
    store: RulesStore = app.state.rules_store
    try:
        await store.save_text(text)
    except rules_file.InvalidRules as e:
        raise ToolError("The rules are not valid, nothing was saved: " + "; ".join(e.messages)) from e
    # end try
    keep_task(app, asyncio.create_task(after_rules_saved(app)))
# end def


async def edit[T](app: FastAPI, change: Callable[[RuleDocument], T]) -> T:
    """Reads the rules, applies `change` to the document and stores the result; one edit at a time."""
    async with app.state.rules_lock:
        document = await read_document(app)
        try:
            result = change(document)
        except EditError as e:
            raise ToolError(e.message) from e
        # end try
        await save_text(app, document.dump())
        return result
    # end async with
# end def


async def view[T](app: FastAPI, read: Callable[[RuleDocument], T]) -> T:
    document = await read_document(app)
    try:
        return read(document)
    except EditError as e:
        raise ToolError(e.message) from e
    # end try
# end def


def redact_dry_run(output: dict[str, Any]) -> dict[str, Any]:
    """Without `mails:read` the affected mails show hashed subjects and reduced addresses."""
    if has_scope(Scope.mails_read):
        return output
    # end if
    for mail in output["mails"]:
        mail["subject"] = redact({"subject": mail["subject"]})["subject"]
        mail["sender"] = mask_sender(mail["sender"])
    # end for
    return output
# end def


def register(server: ScopedServer, app: FastAPI) -> None:
    app.state.rules_lock = asyncio.Lock()

    # --- whole file

    @server.scoped_tool(Scope.rules_read, description="The rules file as YAML text, with comments. Read it before changing anything.")
    async def get_rules_yaml() -> str:
        text = await app.state.rules_store.read_text()
        if text is None:
            raise ToolError("There are no rules yet.")
        # end if
        return text
    # end def

    @server.scoped_tool(Scope.rules_read, description="Checks a rules YAML text without saving it. Returns {valid, messages}.")
    async def validate_rules_yaml(yaml: str) -> dict[str, Any]:
        try:
            await asyncio.to_thread(rules_file.validate, yaml)
        except rules_file.InvalidRules as e:
            return {"valid": False, "messages": e.messages}
        # end try
        return {"valid": True, "messages": []}
    # end def

    @server.scoped_tool(Scope.rules_write, description="Replaces the whole rules file with this YAML text. Invalid text is refused and nothing changes.")
    async def save_rules_yaml(yaml: str) -> str:
        async with app.state.rules_lock:
            await save_text(app, yaml)
        # end async with
        return "saved"
    # end def

    @server.scoped_tool(Scope.rules_read, description="The JSON schema of the rules file: every field, operator and action.")
    async def get_rules_schema() -> dict[str, Any]:
        return json.loads(schema_text())
    # end def

    # --- rules

    @server.scoped_tool(Scope.rules_read, description="All rules in order: index, name, enabled, locations, a one-line summary per action.")
    async def list_rules() -> dict[str, Any]:
        return {"rules": await view(app, lambda document: document.summaries())}
    # end def

    @server.scoped_tool(Scope.rules_read, description="One rule in full, by name.")
    async def get_rule(name: str) -> dict[str, Any]:
        return await view(app, lambda document: plain(document.rule(name)))
    # end def

    @server.scoped_tool(
        Scope.rules_write,
        description="Adds a rule (name, locations, when, actions, optional enabled / description) at a position (default: the end). "
        "A condition may be {type: template, ref: <template name>, variables: {...}}.",
    )
    async def create_rule(rule: dict[str, Any], index: int | None = None) -> dict[str, Any]:
        return {"index": await edit(app, lambda document: document.create_rule(rule, index))}
    # end def

    @server.scoped_tool(
        Scope.rules_write,
        description="Changes some fields of a rule: any of name, description, enabled, locations, when, actions. The given fields are replaced as a whole.",
    )
    async def update_rule(name: str, changes: dict[str, Any]) -> str:
        await edit(app, lambda document: document.update_rule(name, changes))
        return "updated"
    # end def

    @server.scoped_tool(Scope.rules_write, description="Enables or disables a rule.")
    async def set_rule_enabled(name: str, enabled: bool) -> str:
        await edit(app, lambda document: document.update_rule(name, {"enabled": enabled}))
        return "updated"
    # end def

    @server.scoped_tool(Scope.rules_write, description="Moves a rule to another position. The first matching rule wins, so the order matters.")
    async def move_rule(name: str, index: int) -> dict[str, Any]:
        return {"index": await edit(app, lambda document: document.move_rule(name, index))}
    # end def

    @server.scoped_tool(Scope.rules_delete, description="Deletes a rule.")
    async def delete_rule(name: str) -> str:
        await edit(app, lambda document: document.delete_rule(name))
        return "deleted"
    # end def

    # --- conditions

    @server.scoped_tool(
        Scope.rules_read,
        description="A condition of a rule's `when`. The path is a list of child indexes from `when`: [] is `when` itself, [1, 0] is the first "
        "condition of the group that is the second condition. In a `not` only index 0 exists.",
    )
    async def get_condition(rule: str, path: ConditionPath) -> Condition:
        return await view(app, lambda document: document.get_condition(rule, path))
    # end def

    @server.scoped_tool(Scope.rules_write, description="Adds a condition into the all / any group at `path`, at a position (default: the end).")
    async def add_condition(rule: str, path: ConditionPath, condition: Condition, index: int | None = None) -> dict[str, Any]:
        return {"index": await edit(app, lambda document: document.add_condition(rule, path, condition, index))}
    # end def

    @server.scoped_tool(Scope.rules_write, description="Replaces the condition at `path` (the whole `when` for []).")
    async def replace_condition(rule: str, path: ConditionPath, condition: Condition) -> str:
        await edit(app, lambda document: document.replace_condition(rule, path, condition))
        return "replaced"
    # end def

    @server.scoped_tool(Scope.rules_write, description="Wraps the condition at `path` in an all, any or not group.")
    async def wrap_condition(rule: str, path: ConditionPath, combinator: str) -> str:
        await edit(app, lambda document: document.wrap_condition(rule, path, combinator))
        return "wrapped"
    # end def

    @server.scoped_tool(Scope.rules_write, description="Replaces the group at `path` by its children. At the root or inside a not it needs exactly one child.")
    async def unwrap_condition(rule: str, path: ConditionPath) -> str:
        await edit(app, lambda document: document.unwrap_condition(rule, path))
        return "unwrapped"
    # end def

    @server.scoped_tool(Scope.rules_delete, description="Removes the condition at `path` from its all / any group.")
    async def remove_condition(rule: str, path: ConditionPath) -> str:
        await edit(app, lambda document: document.remove_condition(rule, path))
        return "removed"
    # end def

    # --- actions

    @server.scoped_tool(Scope.rules_write, description="Adds an action (move, mark_read, mark_unread, flag, keyword) at a position (default: the end).")
    async def add_action(rule: str, action: dict[str, Any], index: int | None = None) -> dict[str, Any]:
        return {"index": await edit(app, lambda document: document.add_action(rule, action, index))}
    # end def

    @server.scoped_tool(Scope.rules_write, description="Replaces the action at an index.")
    async def replace_action(rule: str, index: int, action: dict[str, Any]) -> str:
        await edit(app, lambda document: document.replace_action(rule, index, action))
        return "replaced"
    # end def

    @server.scoped_tool(Scope.rules_delete, description="Removes the action at an index.")
    async def remove_action(rule: str, index: int) -> str:
        await edit(app, lambda document: document.remove_action(rule, index))
        return "removed"
    # end def

    # --- templates

    @server.scoped_tool(Scope.rules_read, description="Names of the templates.")
    async def list_templates() -> dict[str, Any]:
        return {"templates": await view(app, lambda document: document.template_names())}
    # end def

    @server.scoped_tool(Scope.rules_read, description="One template in full.")
    async def get_template(name: str) -> Any:
        return await view(app, lambda document: document.get_template(name))
    # end def

    @server.scoped_tool(
        Scope.rules_write,
        description="Creates or replaces a template: {content: <condition with {var: name} markers>, defaults?: {...}}. Uses of it keep working.",
    )
    async def save_template(name: str, template: dict[str, Any]) -> str:
        await edit(app, lambda document: document.save_template(name, template))
        return "saved"
    # end def

    @server.scoped_tool(Scope.rules_delete, description="Deletes a template; refused while a rule uses it.")
    async def delete_template(name: str) -> str:
        await edit(app, lambda document: document.delete_template(name))
        return "deleted"
    # end def

    # --- dry run

    @server.scoped_tool(
        Scope.rules_read,
        description="Simulates a rule on the newest mails of its folders (nothing is written to a mailbox or the log). `yaml` takes unsaved rules "
        "text, the stored rules are used without it. Pass back `next` as `cursor` for the following page. "
        "Mail titles and addresses are masked unless the token has mails:read.",
    )
    async def dry_run(rule: str, limit: int = 50, cursor: dict[str, Any] | None = None, yaml: str | None = None) -> dict[str, Any]:
        body = dry_run_api.DryRunIn.model_validate({"rule": rule, "limit": limit, "cursor": cursor, "yaml": yaml})
        async with db_session(app) as session:
            output = await api_call(dry_run_api.post_dry_run(request_of(app), body, session))
        # end with
        return redact_dry_run(output.model_dump(mode="json"))
    # end def
# end def
