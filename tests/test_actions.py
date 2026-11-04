from uuid import UUID

from remote_imap_mail_rules.actions import MovedTo, StepStatus, VirtualWriter, apply_actions, plan_steps, run_chain
from remote_imap_mail_rules.config import ImapSettings
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
        ("move", StepStatus.skipped, "superseded"),
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
    async def move(self, mail: Mail, folder: str, account_id: UUID | None = None) -> MovedTo:
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


CROSS = rules_yaml(rule("r", "invoice", f"""
      - {{type: mark_read}}
      - {{type: move, folder: Inbox2, account_id: {OTHER}}}"""))


def two_servers() -> tuple[FakeServer, FakeServer]:
    source = FakeServer({"IMAP4REV1", "UIDPLUS"})
    source.add("INBOX", 1, "invoice march", flags="Todo", message_id="<m1@example.com>")
    source.folders["INBOX"].messages[0].body = b"the body"
    target = FakeServer({"IMAP4REV1", "UIDPLUS"})
    target.folders["Inbox2"] = FakeFolder(uidvalidity=9)
    target.add("Inbox2", 4, "already there")
    return source, target
# end def


def routed(source: FakeServer, target: FakeServer):  # type: ignore[no-untyped-def]
    def factory(settings: ImapSettings):  # type: ignore[no-untyped-def]
        return (source if settings.imap_account_id == ACCOUNT else target).connect(settings)
    # end def

    async def lookup(account_id: UUID) -> ImapSettings | None:
        return make_settings(imap_account_id=OTHER) if account_id == OTHER else None
    # end def

    return factory, lookup
# end def


async def test_plan_makes_a_move_to_another_account_a_real_step() -> None:
    file = parse_rules(CROSS)
    steps = plan_steps(file.rules[0], await fetch(server(), 1))
    assert [(s.type, s.status) for s in steps] == [("mark_read", StepStatus.planned), ("move", StepStatus.planned)]
    assert steps[-1].args == {"folder": "Inbox2", "account_id": str(OTHER)}
# end def


async def test_a_move_to_another_account_copies_then_deletes() -> None:
    source, target = two_servers()
    factory, lookup = routed(source, target)
    [result] = await apply_actions(make_settings(), parse_rules(CROSS), [await fetch(source, 1)], factory, lookup)
    assert [s.status for s in result.rounds[0].steps] == [StepStatus.done] * 2
    assert result.moved == MovedTo(OTHER, "Inbox2", 5, 9)
    assert source.folders["INBOX"].messages == []
    copy = target.folders["Inbox2"].messages[-1]
    assert (copy.uid, set(copy.flags.split()), copy.body) == (5, {"\\Seen", "Todo"}, b"the body"), "the flags change of the same rule travels along"
    assert b"Subject: invoice march" in copy.raw
# end def


async def test_a_restarted_move_does_not_copy_twice() -> None:
    source, target = two_servers()
    target.add("Inbox2", 5, "invoice march", message_id="<m1@example.com>")
    factory, lookup = routed(source, target)
    [result] = await apply_actions(make_settings(), parse_rules(CROSS), [await fetch(source, 1)], factory, lookup)
    assert result.moved == MovedTo(OTHER, "Inbox2", 5, 9)
    assert [m.uid for m in target.folders["Inbox2"].messages] == [4, 5]
    assert source.folders["INBOX"].messages == []
# end def


async def test_an_unknown_target_account_is_an_error_and_keeps_the_mail() -> None:
    source, target = two_servers()
    factory, _ = routed(source, target)

    async def nobody(account_id: UUID) -> ImapSettings | None:
        return None
    # end def

    [result] = await apply_actions(make_settings(), parse_rules(CROSS), [await fetch(source, 1)], factory, nobody)
    move = result.rounds[0].steps[-1]
    assert (move.status, move.reason) == (StepStatus.error, "unknown_account")
    assert result.moved is None
    assert [m.uid for m in source.folders["INBOX"].messages] == [1]
    assert [m.uid for m in target.folders["Inbox2"].messages] == [4]
# end def


async def test_a_failed_delete_keeps_both_copies_and_reports_where_it_went() -> None:
    source, target = two_servers()
    source.capabilities.discard("UIDPLUS")  # the source cannot expunge one UID safely
    source.capabilities.add("CONDSTORE")
    factory, lookup = routed(source, target)
    [result] = await apply_actions(make_settings(), parse_rules(CROSS), [await fetch(source, 1)], factory, lookup)
    move = result.rounds[0].steps[-1]
    assert (move.status, move.reason) == (StepStatus.error, "source_not_deleted")
    assert result.moved == MovedTo(OTHER, "Inbox2", 5, 9)
    assert [m.uid for m in source.folders["INBOX"].messages] == [1]
    assert [m.uid for m in target.folders["Inbox2"].messages] == [4, 5]
# end def


async def test_the_dry_run_never_touches_either_account() -> None:
    source, target = two_servers()
    commands = len(source.commands), len(target.commands)
    chain = await run_chain(parse_rules(CROSS).rules, await fetch(source, 1), VirtualWriter())
    assert chain.moved == MovedTo(OTHER, "Inbox2")
    assert not any(word in c for c in source.commands[commands[0]:] for word in ("STORE", "APPEND", "EXPUNGE", "SELECT"))
    assert len(target.commands) == commands[1]
# end def
