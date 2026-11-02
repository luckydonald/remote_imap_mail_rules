from pathlib import Path

import pytest
from pydantic import ValidationError

from remote_imap_mail_rules.rules.loader import load_rules, parse_rules
from remote_imap_mail_rules.rules.models import AllExpression
from remote_imap_mail_rules.rules.schema import SCHEMA_PATH, schema_text

EXAMPLE = Path(__file__).resolve().parents[1] / "rules" / "example.yml"


def test_example_loads() -> None:
    rules = load_rules(EXAMPLE)
    assert len(rules.rules) == 1
    rule = rules.rules[0]
    assert len(rule.locations) == 2
    assert rule.locations[0].folder == "INBOX"
    assert rule.locations[1].recursive
    assert isinstance(rule.when, AllExpression)
# end def


def test_committed_schema_is_current() -> None:
    assert SCHEMA_PATH.read_text(encoding="utf-8") == schema_text()
# end def


def test_empty_file() -> None:
    assert parse_rules("").rules == []
# end def


BASE = """
rules:
  - name: r
    locations: [{account_id: 6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11}]
    when: %s
"""


@pytest.mark.parametrize(
    "when",
    [
        "{type: text, field: nonsense, operator: equals, value: x}",
        "{type: text, field: subject, operator: lol, value: x}",
        "{type: text, field: subject, operator: in, value: x}",
        "{type: text, field: subject, operator: equals, value: [x]}",
        "{type: number, field: size, operator: between, value: 3}",
        "{type: number, field: size, operator: gt, value: [1, 2]}",
        "{type: date, field: date_sent, operator: gt, value: {relative: true, value: soon}}",
        "{type: presence}",
        "{type: all, conditions: []}",
        "{type: text, field: subject, operator: equals, value: x, extra: 1}",
    ],
)
def test_invalid_conditions(when: str) -> None:
    with pytest.raises(ValidationError):
        parse_rules(BASE % when)
    # end with
# end def


def test_location_needs_uuid() -> None:
    with pytest.raises(ValidationError):
        parse_rules("rules:\n  - {name: r, locations: [{account_id: my-account}], when: {type: bool, field: seen}}")
    # end with
# end def
