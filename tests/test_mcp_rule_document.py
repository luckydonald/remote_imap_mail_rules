"""Edits of the rules text keep comments and anchors, and the result is still a valid rules file."""

from pathlib import Path

import pytest

from remote_imap_mail_rules.mcp_server.rule_document import EditError, RuleDocument
from remote_imap_mail_rules.rules.loader import parse_rules

ACCOUNT = "6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11"
EXAMPLE = Path(__file__).parent.parent / "rules" / "rules.example.yml"

TEXT = f"""# top comment
templates:
  # explains the template
  from-address: &template-from-address
    type: template
    content:
      type: address
      field: from
      operator: equals
      value: !var sender
rules:
  # first rule
  - name: One
    locations:
      - account_id: {ACCOUNT}
    when:
      type: all
      conditions:
        - type: bool  # seen
          field: seen
        - type: not
          condition:
            type: text
            field: subject
            operator: contains
            value: spam
    actions:
      - type: mark_read
  - name: Two
    locations:
      - account_id: {ACCOUNT}
    when:
      type: bool
      field: flagged
"""


def edited(document: RuleDocument) -> str:
    text = document.dump()
    parse_rules(text)
    return text
# end def


def test_unchanged_document_dumps_identically() -> None:
    assert RuleDocument(TEXT).dump() == TEXT
    assert RuleDocument(EXAMPLE.read_text()).dump() == EXAMPLE.read_text()
# end def


def test_empty_text_starts_an_empty_rule_list() -> None:
    assert RuleDocument(None).summaries() == []
# end def


def test_summaries() -> None:
    summaries = RuleDocument(TEXT).summaries()
    assert [s["name"] for s in summaries] == ["One", "Two"]
    assert summaries[0]["actions"] == ["mark_read"]
# end def


def test_create_update_move_delete_keep_comments() -> None:
    document = RuleDocument(TEXT)
    new = {"name": "Three", "locations": [{"account_id": ACCOUNT}], "when": {"type": "bool", "field": "draft"}}
    assert document.create_rule(new, 1) == 1
    document.update_rule("Two", {"enabled": False, "name": "Two b"})
    assert document.move_rule("Three", 0) == 0
    document.delete_rule("One")
    text = edited(document)
    assert [r.name for r in parse_rules(text).rules] == ["Three", "Two b"]
    assert "# top comment" in text and "# explains the template" in text
# end def


def test_duplicate_and_unknown_names_are_refused() -> None:
    document = RuleDocument(TEXT)
    with pytest.raises(EditError, match="exists already"):
        document.create_rule({"name": "One"})
    # end with
    with pytest.raises(EditError, match="no rule named"):
        document.update_rule("Nope", {})
    # end with
    with pytest.raises(EditError, match="Unknown rule fields"):
        document.update_rule("One", {"colour": "red"})
    # end with
    with pytest.raises(EditError, match="exists already"):
        document.update_rule("One", {"name": "Two"})
    # end with
# end def


def test_conditions_by_path() -> None:
    document = RuleDocument(TEXT)
    assert document.get_condition("One", [0])["field"] == "seen"
    assert document.get_condition("One", [1, 0])["field"] == "subject"
    assert document.add_condition("One", [], {"type": "bool", "field": "answered"}, 1) == 1
    document.replace_condition("One", [2, 0], {"type": "text", "field": "subject", "operator": "contains", "value": "ham"})
    document.remove_condition("One", [0])
    text = edited(document)
    rule = parse_rules(text).rules[0]
    assert [c.type for c in rule.when.conditions] == ["bool", "not"]
    assert "# seen" not in text  # the removed condition's comment goes with it
# end def


def test_condition_errors() -> None:
    document = RuleDocument(TEXT)
    with pytest.raises(EditError, match="No condition 5"):
        document.get_condition("One", [5])
    # end with
    with pytest.raises(EditError, match="only one condition"):
        document.get_condition("One", [1, 1])
    # end with
    with pytest.raises(EditError, match="no children"):
        document.get_condition("One", [0, 0])
    # end with
    with pytest.raises(EditError, match="only to an `all` or `any`"):
        document.add_condition("One", [1], {"type": "bool", "field": "seen"})
    # end with
    with pytest.raises(EditError, match="cannot be removed"):
        document.remove_condition("One", [])
    # end with
    with pytest.raises(EditError, match="cannot be removed"):
        document.remove_condition("One", [1, 0])
    # end with
# end def


def test_wrap_and_unwrap() -> None:
    document = RuleDocument(TEXT)
    document.wrap_condition("Two", [], "not")
    document.wrap_condition("Two", [0], "any")
    assert edited(document) and parse_rules(document.dump()).rules[1].when.type == "not"
    document.unwrap_condition("Two", [0])
    document.unwrap_condition("Two", [])
    assert parse_rules(document.dump()).rules[1].when.type == "bool"
    with pytest.raises(EditError, match="Only a group"):
        document.unwrap_condition("Two", [])
    # end with
    # In a group the children are spliced in at its place.
    document.wrap_condition("One", [0], "all")
    document.unwrap_condition("One", [0])
    assert [c.type for c in parse_rules(document.dump()).rules[0].when.conditions] == ["bool", "not"]
    # At the root a group with several children cannot be unwrapped.
    with pytest.raises(EditError, match="exactly one"):
        document.unwrap_condition("One", [])
    # end with
# end def


def test_actions() -> None:
    document = RuleDocument(TEXT)
    document.add_action("Two", {"type": "move", "folder": "Archive"})
    document.add_action("Two", {"type": "mark_read"}, 0)
    document.replace_action("Two", 1, {"type": "move", "folder": "Other"})
    document.remove_action("One", 0)
    rules = parse_rules(edited(document)).rules
    assert [a.type for a in rules[1].actions] == ["mark_read", "move"] and rules[1].actions[1].folder == "Other"
    assert rules[0].actions == []
    with pytest.raises(EditError, match="No action 4"):
        document.remove_action("Two", 4)
    # end with
# end def


def test_template_use_keeps_the_anchor_and_blocks_deletion() -> None:
    document = RuleDocument(TEXT)
    use = {"type": "template", "ref": "from-address", "variables": {"sender": "a@example.com"}}
    document.add_condition("One", [], use)
    text = edited(document)
    assert "<<: *template-from-address" in text
    assert document.uses_of("from-address") == ["One"]
    with pytest.raises(EditError, match="still used by: One"):
        document.delete_template("from-address")
    # end with
    document.save_template("from-address", {"content": {"type": "address", "field": "to", "operator": "equals", "value": {"var": "sender"}}})
    again = RuleDocument(edited(document))
    assert again.uses_of("from-address") == ["One"]
    document.remove_condition("One", [2])
    document.delete_template("from-address")
    assert "templates" not in edited(document)
# end def


def test_unknown_template_ref() -> None:
    with pytest.raises(EditError, match="no template named"):
        RuleDocument(TEXT).add_condition("One", [], {"type": "template", "ref": "nope"})
    # end with
# end def


def test_new_template() -> None:
    document = RuleDocument(TEXT)
    document.save_template("subject-has", {"content": {"type": "text", "field": "subject", "operator": "contains", "value": {"var": "word"}}})
    document.replace_condition("Two", [], {"type": "template", "ref": "subject-has", "variables": {"word": "hi"}})
    text = edited(document)
    assert "&template-subject-has" in text and document.template_names() == ["from-address", "subject-has"]
# end def
