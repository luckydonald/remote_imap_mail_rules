"""Templates: `Var`, `Template`, `.concrete()` and the `!var` shorthand."""

from datetime import datetime
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from remote_imap_mail_rules.rules.loader import RuleLoader, load_rules, parse_rules
from remote_imap_mail_rules.rules.models import DateCondition, RuleFile, Template, Var
from remote_imap_mail_rules.rules.values import AbsoluteTime, RelativeDuration

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


def date_rule(value: str, defaults: str = "{}", variables: str = "{}", operator: str = "lt") -> str:
    return f"""
templates:
  cutoff: &cutoff
    type: template
    defaults: {defaults}
    content:
      type: date
      field: date_sent
      operator: {operator}
      value: {value}
rules:
  - name: r
    locations: [{{account_id: {ACCOUNT}}}]
    when:
      <<: *cutoff
      variables: {variables}
"""
# end def


@pytest.mark.parametrize(
    ("relative", "default", "override", "expected_default", "expected_override"),
    [
        ("false", "'2026-11-18T08:54:08'", "2026-11-19T08:54:08", datetime(2026, 11, 18, 8, 54, 8), datetime(2026, 11, 19, 8, 54, 8)),
        ("true", "7d", "3w", "7d", "3w"),
    ],
)
def test_date_value_variable_with_fixed_kind(
    relative: str, default: str, override: str, expected_default: datetime | str, expected_override: datetime | str,
) -> None:
    value = f"{{relative: {relative}, value: !var cutoff}}"
    for variables, expected in [("{}", expected_default), (f"{{cutoff: {override}}}", expected_override)]:
        when = parse_rules(date_rule(value, defaults=f"{{cutoff: {default}}}", variables=variables)).rules[0].when
        assert isinstance(when, DateCondition)
        assert isinstance(when.value, RelativeDuration if relative == "true" else AbsoluteTime)
        assert when.value.value == expected
    # end for
# end def


@pytest.mark.parametrize(
    ("variables", "kind", "expected"),
    [
        ("{kind: false, cutoff: '2026-11-18T08:54:08'}", AbsoluteTime, datetime(2026, 11, 18, 8, 54, 8)),
        ("{kind: true, cutoff: 7d}", RelativeDuration, "7d"),
    ],
)
def test_date_kind_and_value_variables(
    variables: str, kind: type[AbsoluteTime] | type[RelativeDuration], expected: datetime | str,
) -> None:
    when = parse_rules(date_rule("{relative: !var kind, value: !var cutoff}", variables=variables)).rules[0].when
    assert isinstance(when, DateCondition)
    assert isinstance(when.value, kind)
    assert when.value.value == expected
# end def


def test_date_range_with_one_variable_value() -> None:
    value = "[{relative: false, value: !var start}, {relative: true, value: 7d}]"
    when = parse_rules(date_rule(value, variables="{start: 2026-10-18T08:54:08}", operator="between")).rules[0].when
    assert isinstance(when, DateCondition)
    assert when.value == (AbsoluteTime(value=datetime(2026, 10, 18, 8, 54, 8)), RelativeDuration(relative=True, value="7d"))
# end def


@pytest.mark.parametrize(
    ("variables", "error"),
    [
        ("{kind: true}", "without value or default: cutoff"),
        ("{cutoff: 7d}", "without value or default: kind"),
        ("{kind: true, cutoff: 7d, extra: 1}", "no such variables: extra"),
        ("{kind: true, cutoff: '2026-11-18T08:54:08'}", "should match pattern"),
        ("{kind: false, cutoff: 7d}", "input should be a valid datetime"),
        ("{kind: 'true', cutoff: 7d}", "needs a boolean"),
    ],
)
def test_date_template_rejects_invalid_bindings(variables: str, error: str) -> None:
    with pytest.raises(ValueError, match=f"(?i){error}"):
        parse_rules(date_rule("{relative: !var kind, value: !var cutoff}", variables=variables))
    # end with
# end def


def test_whole_date_value_variable_still_resolves() -> None:
    when = parse_rules(date_rule("!var time", variables="{time: {relative: true, value: 7d}}")).rules[0].when
    assert isinstance(when, DateCondition)
    assert when.value == RelativeDuration(relative=True, value="7d")
# end def


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


NESTED_HEAD = """
templates:
  inner: &inner
    type: template
    content: {{type: text, field: subject, operator: contains, value: {{var: word}}}}
  outer: &outer
    type: template
    defaults: {{topic: news}}
    content:
      <<: *inner
      variables: {{word: {{var: topic}}}}
rules:
  - name: r
    locations: [{{account_id: {ACCOUNT}}}]
    when:
      <<: *outer
"""


def test_nested_template_uses_default_of_the_outer_one() -> None:
    assert parse_rules(NESTED_HEAD.format(ACCOUNT=ACCOUNT)).rules[0].when.value == "news"
# end def


def test_nested_template_outer_variable_without_value_is_refused() -> None:
    text = NESTED_HEAD.format(ACCOUNT=ACCOUNT).replace("defaults: {topic: news}", "")
    with pytest.raises(ValueError, match="topic"):
        parse_rules(text)
    # end with
# end def


def test_nothing_templated_is_left_after_loading() -> None:
    dumped = load_rules(EXAMPLE).model_dump_json()
    assert '"template"' not in dumped
    assert '"var"' not in dumped


def test_types_are_importable() -> None:
    assert Var(var="x").var == "x"
    assert Template.model_fields["type"].default == "template"
