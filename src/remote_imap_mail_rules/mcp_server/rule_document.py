"""Edits of the rules text that keep comments, anchors and `!var`: a ruamel round-trip document, changed in place and dumped again.

Everything here is text in, text out and synchronous; validating the result and storing it is the caller's job.
A condition is addressed by a path of child indexes from the rule's `when`: `[]` is `when` itself, in an `all` / `any` an index picks
`conditions[i]`, in a `not` only `0` (its `condition`) is valid.
"""

import copy
import io
from collections.abc import Mapping, Sequence
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.mergevalue import MergeValue

GROUPS = ("all", "any")
COMBINATORS = ("all", "any", "not")


class EditError(Exception):
    """The edit cannot be done, `message` says why in terms of the rules."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message
    # end def
# end class


def make_yaml() -> YAML:
    yaml = YAML(typ="rt")
    yaml.preserve_quotes = True
    yaml.width = 4096
    yaml.indent(mapping=2, sequence=4, offset=2)
    return yaml
# end def


def plain(node: Any) -> Any:
    """The node as plain dicts, lists and scalars (merge keys are expanded), for answers to the client."""
    if isinstance(node, Mapping):
        return {str(key): plain(value) for key, value in node.items()}
    # end if
    if isinstance(node, Sequence) and not isinstance(node, str):
        return [plain(item) for item in node]
    # end if
    if hasattr(node, "tag") and hasattr(node, "value"):  # `!var name`
        return {"var": str(node.value)}
    # end if
    if isinstance(node, bool) or node is None:
        return node
    # end if
    if isinstance(node, int):
        return int(node)
    # end if
    if isinstance(node, float):
        return float(node)
    # end if
    return str(node) if not isinstance(node, str) else str(node)
# end def


def is_group(node: Any) -> bool:
    return isinstance(node, Mapping) and node.get("type") in GROUPS
# end def


def keep_anchors(node: Any) -> None:
    """ruamel drops an anchor nothing points to; a template without a use in the rules must keep its anchor."""
    anchor = getattr(node, "anchor", None)
    if anchor is not None and getattr(anchor, "value", None) is not None:
        anchor.always_dump = True
    # end if
    if isinstance(node, Mapping):
        for value in node.values():
            keep_anchors(value)
        # end for
    elif isinstance(node, list):
        for value in node:
            keep_anchors(value)
        # end for
    # end if
# end def


class RuleDocument:
    def __init__(self, text: str | None) -> None:
        self.yaml = make_yaml()
        loaded = self.yaml.load(text) if text and text.strip() else None
        if loaded is None:
            loaded = CommentedMap()
        # end if
        if not isinstance(loaded, CommentedMap):
            raise EditError("The rules text is not a mapping.")
        # end if
        self.root: CommentedMap = loaded
        keep_anchors(self.root)
        if self.root.get("rules") is None:
            self.root["rules"] = CommentedSeq()
        # end if
    # end def

    def dump(self) -> str:
        stream = io.StringIO()
        self.yaml.dump(self.root, stream)
        return stream.getvalue()
    # end def

    @property
    def rules(self) -> CommentedSeq:
        rules = self.root["rules"]
        if not isinstance(rules, CommentedSeq):
            raise EditError("`rules` is not a list.")
        # end if
        return rules
    # end def

    @property
    def templates(self) -> CommentedMap:
        if self.root.get("templates") is None:
            self.root["templates"] = CommentedMap()
        # end if
        return self.root["templates"]
    # end def

    # --- rules

    def index_of(self, name: str) -> int:
        matches = [index for index, rule in enumerate(self.rules) if rule.get("name") == name]
        if not matches:
            raise EditError(f"There is no rule named {name!r}.")
        # end if
        if len(matches) > 1:
            raise EditError(f"There are {len(matches)} rules named {name!r}, rename them first.")
        # end if
        return matches[0]
    # end def

    def rule(self, name: str) -> CommentedMap:
        return self.rules[self.index_of(name)]
    # end def

    def summaries(self) -> list[dict[str, Any]]:
        return [
            {
                "index": index,
                "name": rule.get("name"),
                "enabled": plain(rule.get("enabled", True)),
                "locations": plain(rule.get("locations", [])),
                "actions": [self.describe_action(action) for action in rule.get("actions") or []],
            }
            for index, rule in enumerate(self.rules)
        ]
    # end def

    @staticmethod
    def describe_action(action: Any) -> str:
        kind = action.get("type")
        detail = action.get("folder") or action.get("keyword") or ""
        return f"{kind} {detail}".strip()
    # end def

    def create_rule(self, rule: Mapping[str, Any], index: int | None = None) -> int:
        name = rule.get("name")
        if not name or not isinstance(name, str):
            raise EditError("A rule needs a `name`.")
        # end if
        if any(existing.get("name") == name for existing in self.rules):
            raise EditError(f"A rule named {name!r} exists already.")
        # end if
        position = self.position(index, len(self.rules))
        self.rules.insert(position, self.node(rule))
        return position
    # end def

    def update_rule(self, name: str, changes: Mapping[str, Any]) -> None:
        rule = self.rule(name)
        unknown = set(changes) - {"name", "description", "enabled", "locations", "when", "actions"}
        if unknown:
            raise EditError(f"Unknown rule fields: {', '.join(sorted(unknown))}.")
        # end if
        new_name = changes.get("name")
        if new_name is not None and new_name != name and any(existing.get("name") == new_name for existing in self.rules):
            raise EditError(f"A rule named {new_name!r} exists already.")
        # end if
        for key, value in changes.items():
            if value is None and key in ("description",):
                rule.pop(key, None)
            else:
                rule[key] = self.node(value)
            # end if
        # end for
    # end def

    def move_rule(self, name: str, index: int) -> int:
        current = self.index_of(name)
        rule = self.rules.pop(current)
        position = self.position(index, len(self.rules))
        self.rules.insert(position, rule)
        return position
    # end def

    def delete_rule(self, name: str) -> None:
        del self.rules[self.index_of(name)]
    # end def

    # --- conditions

    def walk(self, rule_name: str, path: Sequence[int]) -> tuple[Any, str | int | None, Any]:
        """`(parent, key in parent, node)` of the condition at `path`; the parent of `when` is the rule."""
        rule = self.rule(rule_name)
        if "when" not in rule:
            raise EditError(f"The rule {rule_name!r} has no `when`.")
        # end if
        parent: Any = rule
        key: str | int = "when"
        node = rule["when"]
        for step in path:
            if is_group(node):
                children = node["conditions"]
                if not 0 <= step < len(children):
                    raise EditError(f"No condition {step} here, the group has {len(children)}.")
                # end if
                parent, key, node = children, step, children[step]
            elif isinstance(node, Mapping) and node.get("type") == "not":
                if step != 0:
                    raise EditError("A `not` has only one condition, path index 0.")
                # end if
                parent, key, node = node, "condition", node["condition"]
            else:
                raise EditError(f"The condition of type {node.get('type')!r} has no children.")
            # end if
        # end for
        return parent, key, node
    # end def

    def get_condition(self, rule_name: str, path: Sequence[int]) -> Any:
        return plain(self.walk(rule_name, path)[2])
    # end def

    def add_condition(self, rule_name: str, path: Sequence[int], condition: Mapping[str, Any], index: int | None = None) -> int:
        _, _, group = self.walk(rule_name, path)
        if not is_group(group):
            raise EditError("Conditions can be added only to an `all` or `any` group; use replace_condition or wrap_condition.")
        # end if
        position = self.position(index, len(group["conditions"]))
        group["conditions"].insert(position, self.node(condition))
        return position
    # end def

    def replace_condition(self, rule_name: str, path: Sequence[int], condition: Mapping[str, Any]) -> None:
        parent, key, _ = self.walk(rule_name, path)
        parent[key] = self.node(condition)
    # end def

    def remove_condition(self, rule_name: str, path: Sequence[int]) -> None:
        if not path:
            raise EditError("The rule's `when` cannot be removed, replace it instead.")
        # end if
        parent, key, _ = self.walk(rule_name, path)
        if not isinstance(parent, CommentedSeq):
            raise EditError("The only condition of a `not` cannot be removed, remove the `not` or replace the condition.")
        # end if
        del parent[key]
    # end def

    def wrap_condition(self, rule_name: str, path: Sequence[int], combinator: str) -> None:
        if combinator not in COMBINATORS:
            raise EditError(f"The combinator must be one of {', '.join(COMBINATORS)}.")
        # end if
        parent, key, node = self.walk(rule_name, path)
        wrapper = CommentedMap()
        wrapper["type"] = combinator
        if combinator == "not":
            wrapper["condition"] = node
        else:
            wrapper["conditions"] = CommentedSeq([node])
        # end if
        parent[key] = wrapper
    # end def

    def unwrap_condition(self, rule_name: str, path: Sequence[int]) -> None:
        parent, key, node = self.walk(rule_name, path)
        if isinstance(node, Mapping) and node.get("type") == "not":
            children = [node["condition"]]
        elif is_group(node):
            children = list(node["conditions"])
        else:
            raise EditError("Only a group (`all`, `any`, `not`) can be unwrapped.")
        # end if
        if isinstance(parent, CommentedSeq):
            parent[key : key + 1] = children  # type: ignore[misc]  # splice into the parent group
        elif len(children) == 1:
            parent[key] = children[0]
        else:
            raise EditError("At the root or inside a `not` only a group with exactly one condition can be unwrapped.")
        # end if
    # end def

    # --- actions

    def actions(self, rule_name: str) -> CommentedSeq:
        rule = self.rule(rule_name)
        if rule.get("actions") is None:
            rule["actions"] = CommentedSeq()
        # end if
        return rule["actions"]
    # end def

    def add_action(self, rule_name: str, action: Mapping[str, Any], index: int | None = None) -> int:
        actions = self.actions(rule_name)
        position = self.position(index, len(actions))
        actions.insert(position, self.node(action))
        return position
    # end def

    def replace_action(self, rule_name: str, index: int, action: Mapping[str, Any]) -> None:
        actions = self.actions(rule_name)
        self.check_index(index, len(actions), "action")
        actions[index] = self.node(action)
    # end def

    def remove_action(self, rule_name: str, index: int) -> None:
        actions = self.actions(rule_name)
        self.check_index(index, len(actions), "action")
        del actions[index]
    # end def

    # --- templates

    def template_names(self) -> list[str]:
        return [str(name) for name in (self.root.get("templates") or {})]
    # end def

    def get_template(self, name: str) -> Any:
        templates = self.root.get("templates") or {}
        if name not in templates:
            raise EditError(f"There is no template named {name!r}.")
        # end if
        return plain(templates[name])
    # end def

    def save_template(self, name: str, template: Mapping[str, Any]) -> None:
        templates = self.templates
        new = self.node({"type": "template", **template})
        if name in templates:
            old = templates[name]
            # Keep the anchor, so the uses in the rules still point here.
            old_anchor = old.yaml_anchor() if hasattr(old, "yaml_anchor") else None
            if old_anchor is not None:
                new.yaml_set_anchor(old_anchor.value, always_dump=True)
            # end if
            old.clear()
            for key, value in new.items():
                old[key] = value
            # end for
        else:
            new.yaml_set_anchor(f"template-{name}".replace(".", "-"), always_dump=True)
            templates[name] = new
        # end if
    # end def

    def uses_of(self, name: str) -> list[str]:
        """Names of the rules that use the template (through a merge of its map, or an expanded copy of its content)."""
        templates = self.root.get("templates") or {}
        if name not in templates:
            return []
        # end if
        target = templates[name]
        content = plain(target.get("content"))
        found: list[str] = []

        def visit(node: Any) -> bool:
            if isinstance(node, CommentedMap):
                if any(source is target for source in getattr(node, "merge", None) or []):
                    return True
                # end if
                # The database keeps a use expanded, without the link to its template: the same content counts as a use.
                if node.get("type") == "template" and "content" in node and plain(node["content"]) == content:
                    return True
                # end if
                return any(visit(value) for value in node.values())
            # end if
            if isinstance(node, CommentedSeq):
                return any(visit(item) for item in node)
            # end if
            return False
        # end def

        for rule in self.rules:
            if visit(rule.get("when")):
                found.append(str(rule.get("name")))
            # end if
        # end for
        return found
    # end def

    def delete_template(self, name: str) -> None:
        templates = self.root.get("templates") or {}
        if name not in templates:
            raise EditError(f"There is no template named {name!r}.")
        # end if
        used = self.uses_of(name)
        if used:
            raise EditError(f"The template {name!r} is still used by: {', '.join(used)}.")
        # end if
        del templates[name]
        if not templates:
            del self.root["templates"]
        # end if
    # end def

    # --- helpers

    def node(self, value: Any) -> Any:
        """Plain data as ruamel nodes; `{type: template, ref, variables}` becomes a real use (`<<: *anchor` plus `variables`)."""
        if isinstance(value, Mapping):
            if value.get("type") == "template" and "ref" in value:
                return self.template_use(value)
            # end if
            result = CommentedMap()
            for key, item in value.items():
                result[key] = self.node(item)
            # end for
            return result
        # end if
        if isinstance(value, (list, tuple)):
            return CommentedSeq(self.node(item) for item in value)
        # end if
        return copy.copy(value)
    # end def

    def template_use(self, value: Mapping[str, Any]) -> CommentedMap:
        name = value["ref"]
        templates = self.root.get("templates") or {}
        if name not in templates:
            raise EditError(f"There is no template named {name!r}.")
        # end if
        source = templates[name]
        if source.yaml_anchor() is None:
            source.yaml_set_anchor(f"template-{name}".replace(".", "-"), always_dump=True)
        # end if
        use = CommentedMap()
        merged = MergeValue()
        merged.append(source)
        merged.merge_pos = 0
        use.add_yaml_merge(merged)
        if value.get("variables"):
            use["variables"] = self.node(value["variables"])
        # end if
        return use
    # end def

    @staticmethod
    def position(index: int | None, length: int) -> int:
        if index is None:
            return length
        # end if
        if not 0 <= index <= length:
            raise EditError(f"The position {index} is outside 0 to {length}.")
        # end if
        return index
    # end def

    @staticmethod
    def check_index(index: int, length: int, what: str) -> None:
        if not 0 <= index < length:
            raise EditError(f"No {what} {index}, there are {length}.")
        # end if
    # end def
# end class
