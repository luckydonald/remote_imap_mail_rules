"""Templates: `Var`, `Template`, `.concrete()` and the `!var` shorthand."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from remote_imap_mail_rules.rules.loader import RuleLoader, load_rules, parse_rules
from remote_imap_mail_rules.rules.models import RuleFile, Template, Var

ACCOUNT = "6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11"
EXAMPLE = Path(__file__).resolve().parents[1] / "rules" / "rules.example.yml"

TEMPLATE = """
templates:
  forward: &forward
    type: template
    defaults: {name: " 'x'"}
    content:
      type: all
      conditions:
        - {type: address, field: from, operator: equals, value: !var addr}
        - {type: address, field: from, part: name, operator: endswith, value: {var: name}}
"""


def rule(when: str) -> str:
    return TEMPLATE + f"""
rules:
  - name: r
    locations: [{{account_id: {ACCOUNT}}}]
    when:
{when}
"""


PLAIN = f"""
rules:
  - name: r
    locations: [{{account_id: {ACCOUNT}}}]
    when:
      type: all
      conditions:
        - {{type: address, field: from, operator: equals, value: a@b.c}}
        - {{type: address, field: from, part: name, operator: endswith, value: " 'x'"}}
"""


def test_template_equals_written_out_rule() -> None:
    templated = parse_rules(rule("      <<: *forward\n      variables: {addr: a@b.c}"))
    plain = parse_rules(PLAIN)
    assert templated.rules[0].when == plain.rules[0].when
    assert templated.templates == {}


def test_variable_overrides_default() -> None:
    result = parse_rules(rule("      <<: *forward\n      variables: {addr: a@b.c, name: ' y'}"))
    assert result.rules[0].when.conditions[1].value == " y"


def test_var_tag_and_mapping_are_the_same() -> None:
    assert yaml.load("!var x", Loader=RuleLoader) == {"var": "x"}


def test_missing_variable_fails_validation_not_only_concrete() -> None:
    with pytest.raises(ValidationError, match="without value or default: addr"):
        parse_rules(rule("      <<: *forward\n      variables: {}"))


def test_unknown_variable_fails() -> None:
    with pytest.raises(ValidationError, match="no such variables: nope"):
        parse_rules(rule("      <<: *forward\n      variables: {addr: a, nope: 1}"))


def test_definition_may_leave_variables_unfilled() -> None:
    # the definition has `addr` unset, it is only checked where it is used
    file = RuleFile.model_validate(yaml.load(TEMPLATE, Loader=RuleLoader))
    assert "forward" in file.templates


def test_var_outside_a_template_fails() -> None:
    text = PLAIN.replace("value: a@b.c", "value: {var: nowhere}")
    with pytest.raises(ValueError, match="nowhere"):
        parse_rules(text)


def test_var_on_number_and_operator() -> None:
    text = f"""
templates:
  big: &big
    type: template
    content: {{type: number, field: size, operator: {{var: op}}, value: {{var: limit}}}}
rules:
  - name: r
    locations: [{{account_id: {ACCOUNT}}}]
    when:
      <<: *big
      variables: {{op: gt, limit: 5000}}
"""
    when = parse_rules(text).rules[0].when
    assert (when.operator, when.value) == ("gt", 5000)


def test_nested_template_gets_outer_variable() -> None:
    text = f"""
templates:
  inner: &inner
    type: template
    content: {{type: text, field: subject, operator: contains, value: {{var: word}}}}
  outer: &outer
    type: template
    content:
      type: not
      condition:
        <<: *inner
        variables: {{word: {{var: topic}}}}
rules:
  - name: r
    locations: [{{account_id: {ACCOUNT}}}]
    when:
      <<: *outer
      variables: {{topic: spam}}
"""
    when = parse_rules(text).rules[0].when
    assert when.condition.value == "spam"


def test_nothing_templated_is_left_after_loading() -> None:
    dumped = load_rules(EXAMPLE).model_dump_json()
    assert '"template"' not in dumped
    assert '"var"' not in dumped


def test_types_are_importable() -> None:
    assert Var(var="x").var == "x"
    assert Template.model_fields["type"].default == "template"
