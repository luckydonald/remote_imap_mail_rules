"""Rules and templates as rows: one row per rule, one per template."""

from typing import Any
from uuid import uuid4

import yaml
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from ..rules.models import Rule as RuleModel
from ..rules.models import RuleFile, TemplateDefinition, Var
from .models import Rule, Template


def dump(model: Any) -> Any:
    """JSON-compatible data, `Var` stays `{var: name}` so template variables survive."""
    return model.model_dump(mode="json", exclude_none=True)
# end def


async def load_rule_file(session: AsyncSession) -> RuleFile[Var] | None:
    """The stored rule file, or `None` when nothing is stored yet."""
    rows = list((await session.scalars(select(Rule).order_by(Rule.position))).all())
    templates = list((await session.scalars(select(Template).order_by(Template.name))).all())
    if not rows and not templates:
        return None
    # end if
    return RuleFile[Var].model_validate(
        {
            "templates": {template.name: template.definition for template in templates},
            "rules": [{"name": r.name, "enabled": r.enabled, "locations": r.locations, "when": r.when, "actions": r.actions} for r in rows],
        }
    )
# end def


async def replace_rule_file(session: AsyncSession, rule_file: RuleFile[Var]) -> None:
    """Makes the rows equal `rule_file`. A rule keeps its id when a rule of that name already exists."""
    old = list((await session.scalars(select(Rule))).all())
    by_name: dict[str, list[Rule]] = {}
    for row in old:
        by_name.setdefault(row.name, []).append(row)
    # end for
    kept: set[Any] = set()
    for position, rule in enumerate(rule_file.rules):
        candidates = by_name.get(rule.name)
        row = candidates.pop(0) if candidates else None
        if row is None:
            row = Rule(id=uuid4())
            session.add(row)
        # end if
        kept.add(row.id)
        fill_rule(row, position, rule)
    # end for
    for row in old:
        if row.id not in kept:
            await session.delete(row)
        # end if
    # end for
    await session.execute(delete(Template))
    for name, definition in rule_file.templates.items():
        session.add(Template(name=name, definition=dump_template(definition)))
    # end for
    await session.flush()
# end def


def fill_rule(row: Rule, position: int, rule: RuleModel[Var]) -> None:
    data = dump(rule)
    row.position = position
    row.name = data["name"]
    row.enabled = data["enabled"]
    row.locations = data["locations"]
    row.when = data["when"]
    row.actions = data.get("actions", [])
# end def


def dump_template(definition: TemplateDefinition) -> dict[str, Any]:
    data: dict[str, Any] = dump(definition)
    return data
# end def


def to_yaml(rule_file: RuleFile[Var]) -> str:
    return yaml.safe_dump(dump(rule_file), sort_keys=False, allow_unicode=True)
# end def
