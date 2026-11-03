from uuid import UUID

from remote_imap_mail_rules.actions import StepStatus, VirtualWriter, apply_actions, plan_steps, run_chain
from remote_imap_mail_rules.imap.client import ImapClient, ImapError
from remote_imap_mail_rules.mail import Mail
from remote_imap_mail_rules.rules.loader import parse_rules

from .fake_imap import FakeFolder, FakeServer
from .test_imap import ACCOUNT, make_settings

OTHER = UUID("0b8d3f4c-2b6e-4f0e-8f4a-3c8f6f1e9d22")


def rules_yaml(*rules: str) -> str:
    return "rules:\n" + "\n".join(rules)
# end def


def rule(name: str, subject: str, actions: str, extra: str = "") -> str:
    return f"""
  - name: {name}
    locations: [{{account_id: {ACCOUNT}}}]
    when:
      type: all
      conditions:
        - {{type: text, field: subject, operator: contains, value: {subject}}}
{extra}
    actions:
{actions}"""
# end def


def server() -> FakeServer:
    fake = FakeServer({"IMAP4REV1", "MOVE", "CONDSTORE"})
    fake.add("INBOX", 1, "invoice march")
    fake.add("INBOX", 2, "hello")
    fake.folders["Archive"] = FakeFolder()
    return fake
# end def


def flags(fake: FakeServer, folder: str, uid: int) -> set[str]:
    return set(next(m for m in fake.folders[folder].messages if m.uid == uid).flags.split())
# end def


async def fetch(fake: FakeServer, uid: int) -> Mail:
    async with ImapClient(make_settings(), fake.connect) as client:
        mail = await client.fetch_message(ACCOUNT, "INBOX", uid)
    assert mail is not None
    return mail
# end def


async def test_plan_marks_noops_and_puts_the_move_last() -> None:
    file = parse_rules(rules_yaml(rule("r", "invoice", f"""
      - {{type: move, folder: Archive}}
      - {{type: mark_read}}
      - {{type: move, folder: Other}}
      - {{type: flag, value: false}}
      - {{type: move, folder: Elsewhere, account_id: {OTHER}}}""")))
    mail = await fetch(server(), 1)
    steps = plan_steps(file.rules[0], mail)
    assert [(s.type, s.status, s.reason) for s in steps] == [
        ("mark_read", StepStatus.planned, None),
        ("move", StepStatus.skipped, "superseded"),
        ("flag", StepStatus.noop, "already"),
        ("move", StepStatus.skipped, "cross_account_not_supported"),
        ("move", StepStatus.planned, None),
    ]
    assert steps[-1].args == {"folder": "Archive"}
# end def


async def test_apply_changes_the_mailbox() -> None:
    fake = server()
    file = parse_rules(rules_yaml(rule("r", "invoice", """
      - {type: mark_read}
      - {type: flag}
      - {type: keyword, keyword: Todo}
      - {type: move, folder: Archive}""")))
    [result] = await apply_actions(make_settings(), file, [await fetch(fake, 1)], fake.connect)
    assert result.moved_to == "Archive"
    assert [m.uid for m in fake.folders["INBOX"].messages] == [2]
    assert flags(fake, "Archive", 1) == {"\\Seen", "\\Flagged", "Todo"}
    assert [s.status for s in result.rounds[0].steps] == [StepStatus.done] * 4
# end def


async def test_first_matching_rule_wins() -> None:
    fake = server()
    file = parse_rules(rules_yaml(
        rule("first", "invoice", "      - {type: mark_read}"),
        rule("second", "invoice", "      - {type: move, folder: Archive}"),
    ))
    [result] = await apply_actions(make_settings(), file, [await fetch(fake, 1)], fake.connect)
    assert [r.rule.name for r in result.rounds] == ["first"]
    assert [m.uid for m in fake.folders["INBOX"].messages] == [1, 2]
    assert flags(fake, "INBOX", 1) == {"\\Seen"}
# end def


async def test_rules_are_evaluated_again_after_a_change() -> None:
    """`first` marks the mail read, which stops it from matching, so `second` wins in the next round."""
    fake = server()
    file = parse_rules(rules_yaml(
        rule("first", "invoice", "      - {type: mark_read}", "        - {type: bool, field: seen, value: false}"),
        rule("second", "invoice", "      - {type: move, folder: Archive}"),
    ))
    [result] = await apply_actions(make_settings(), file, [await fetch(fake, 1)], fake.connect)
    assert [r.rule.name for r in result.rounds] == ["first", "second"]
    assert result.moved_to == "Archive"
    assert flags(fake, "Archive", 1) == {"\\Seen"}
# end def


async def test_a_noop_winner_stops_the_chain() -> None:
    fake = server()
    fake.set_flags("INBOX", 1, "\\Seen")
    file = parse_rules(rules_yaml(
        rule("first", "invoice", "      - {type: mark_read}"),
        rule("second", "invoice", "      - {type: move, folder: Archive}"),
    ))
    commands = len(fake.commands)
    [result] = await apply_actions(make_settings(), file, [await fetch(fake, 1)], fake.connect)
    assert result.rounds[0].steps[0].status == StepStatus.noop and len(result.rounds) == 1
    assert not any("STORE" in c or "MOVE" in c for c in fake.commands[commands:])
# end def


class FailingMove(VirtualWriter):
    async def move(self, mail: Mail, folder: str) -> None:
        raise ImapError("no such folder")
    # end def
# end class


async def test_errors_are_reported_and_stop_later_steps() -> None:
    fake = server()
    file = parse_rules(rules_yaml(rule("r", "invoice", """
      - {type: move, folder: Missing}
      - {type: mark_read}""")))
    chain = await run_chain(file.rules, await fetch(fake, 1), FailingMove())
    assert [(s.type, s.status) for s in chain.rounds[0].steps] == [("mark_read", StepStatus.done), ("move", StepStatus.error)]
    assert chain.moved_to is None
# end def


async def test_virtual_writer_changes_nothing() -> None:
    fake = server()
    file = parse_rules(rules_yaml(rule("r", "invoice", "      - {type: move, folder: Archive}")))
    commands = len(fake.commands)
    chain = await run_chain(file.rules, await fetch(fake, 1), VirtualWriter())
    assert chain.moved_to == "Archive"
    assert not any(word in c for c in fake.commands[commands:] for word in ("STORE", "MOVE", "COPY", "EXPUNGE", "SELECT"))
# end def
