"""Comments of a rule are rescued into its description."""

from remote_imap_mail_rules.rules.comments import append_comments, comment_lines
from remote_imap_mail_rules.rules.loader import parse_rule_file

ACCOUNT = "6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11"

TEXT = f"""# header, not a rule comment
rules:
  # about one
  # more about one

  - name: One
    # inside one
    locations:
      - account_id: {ACCOUNT}
    when:
      type: text
      field: body_text
      operator: regex
      value: |
        # not a comment, a regex line
        x
    actions: []
  # about two
  - name: Two
    description: Existing.
    locations:
      - account_id: {ACCOUNT}
    when: {{type: bool, field: seen}}
"""


def test_comment_lines_per_rule() -> None:
    assert comment_lines(TEXT) == [["# about one", "# more about one", "# inside one"], ["# about two"]]
# end def


def test_append_to_description() -> None:
    rule_file = append_comments(TEXT, parse_rule_file(TEXT))
    one, two = rule_file.rules
    assert one.description == "# about one\n# more about one\n# inside one"
    assert two.description == "Existing.\n# about two"
# end def


def test_appending_twice_adds_nothing() -> None:
    once = append_comments(TEXT, parse_rule_file(TEXT))
    twice = append_comments(TEXT, once)
    assert [r.description for r in twice.rules] == [r.description for r in once.rules]
# end def


def test_no_rules_or_comments() -> None:
    assert comment_lines("rules: []\n") == []
    assert comment_lines("") == []
    plain = "rules:\n  - name: A\n    locations: [{account_id: %s}]\n    when: {type: bool, field: seen}\n" % ACCOUNT
    assert append_comments(plain, parse_rule_file(plain)).rules[0].description is None
# end def
