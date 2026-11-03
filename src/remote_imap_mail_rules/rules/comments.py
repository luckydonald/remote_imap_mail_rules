"""Rescuing the comments of a rule file into the `description` of the rules.

PyYAML drops comments, so a store that keeps parsed rules (the database) would lose them.
Only full-line comments are taken: the block directly above a rule and the ones inside it.
Trailing comments (`key: value  # note`) and comments outside the rules (file header, `templates`) are not.
"""

from typing import Any

import yaml

from .loader import RuleLoader
from .models import RuleFile, Var


def scalar_lines(text: str) -> set[int]:
    """Lines inside multi-line scalars, where a leading `#` is content, not a comment."""
    lines: set[int] = set()
    for token in yaml.scan(text, Loader=RuleLoader):
        if isinstance(token, yaml.ScalarToken) and token.end_mark.line > token.start_mark.line:
            lines.update(range(token.start_mark.line + 1, token.end_mark.line + 1))
        # end if
    # end for
    return lines
# end def


def rule_starts(text: str) -> tuple[list[int], int]:
    """The 0-based first line of every rule, and the line where the `rules` sequence ends."""
    root = yaml.compose(text, Loader=RuleLoader)
    if not isinstance(root, yaml.MappingNode):
        return [], 0
    # end if
    for key, value in root.value:
        if key.value == "rules" and isinstance(value, yaml.SequenceNode):
            return [item.start_mark.line for item in value.value], value.end_mark.line + 1
        # end if
    # end for
    return [], 0
# end def


def comment_lines(text: str) -> list[list[str]]:
    """The full-line comments of every rule, in file order, blank lines dropped."""
    starts, end = rule_starts(text)
    if not starts:
        return []
    # end if
    lines = text.splitlines()
    content = scalar_lines(text)

    def is_comment(index: int) -> bool:
        return index not in content and lines[index].lstrip().startswith("#")
    # end def

    def is_blank(index: int) -> bool:
        return index not in content and lines[index].strip() == ""
    # end def

    # The block directly above a rule (comments and blanks) belongs to that rule, not to the one before.
    above: list[int] = []
    for start in starts:
        top = start
        while top > 0 and (is_comment(top - 1) or is_blank(top - 1)):
            top -= 1
        # end while
        above.append(top)
    # end for
    result: list[list[str]] = []
    for i, start in enumerate(starts):
        stop = above[i + 1] if i + 1 < len(starts) else min(max(end, start + 1), len(lines))
        span = [*range(above[i], start), *range(start, stop)]
        result.append([lines[n].strip() for n in span if is_comment(n)])
    # end for
    return result
# end def


def append_comments(text: str, rule_file: RuleFile[Var]) -> RuleFile[Var]:
    """Appends each rule's comments to its `description`, one line each, skipping lines it already has."""
    found = comment_lines(text)
    rules = []
    for rule, comments in zip(rule_file.rules, found, strict=False):
        description = rule.description or ""
        have = set(description.splitlines())
        new = [comment for comment in comments if comment not in have]
        if new:
            description = "\n".join([*([description] if description else []), *new])
            rule = rule.model_copy(update={"description": description})
        # end if
        rules.append(rule)
    # end for
    rules.extend(rule_file.rules[len(rules) :])
    return rule_file.model_copy(update={"rules": rules})
# end def


def literal_str_representer(dumper: yaml.SafeDumper, data: str) -> Any:
    """Multi-line strings as `|` blocks, so a description reads as lines instead of one escaped string."""
    return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|" if "\n" in data else None)
# end def
