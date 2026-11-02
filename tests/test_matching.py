import asyncio
import logging
from collections.abc import AsyncIterator
from uuid import UUID

import pytest

from remote_imap_mail_rules.matching import MatchKind, RuleMatch, matches
from remote_imap_mail_rules.rules.loader import parse_rules

from .fake_imap import FakeServer
from .test_imap import ACCOUNT, make_settings

OTHER = UUID("0b8d3f4c-2b6e-4f0e-8f4a-3c8f6f1e9d22")

RULES = f"""
rules:
  - name: unread invoices
    locations:
      - account_id: {ACCOUNT}
      - account_id: {ACCOUNT}
        folder: Lists
        recursive: true
      - account_id: {OTHER}
        folder: Elsewhere
    when:
      type: all
      conditions:
        - type: text
          field: subject
          operator: contains
          value: invoice
        - type: bool
          field: seen
          value: false
  - name: disabled
    enabled: false
    locations: [{{account_id: {ACCOUNT}}}]
    when: {{type: bool, field: seen}}
"""


async def take(generator: AsyncIterator[RuleMatch], count: int) -> list[RuleMatch]:
    return [await asyncio.wait_for(anext(generator), 2) for _ in range(count)]
# end def


async def test_existing_matches_across_locations_and_recursion() -> None:
    server = FakeServer()
    server.add("INBOX", 1, "Invoice 1")
    server.add("INBOX", 2, "hello")
    server.add("INBOX", 3, "invoice 3", flags="\\Seen")
    server.add("Lists", 1, "invoice list parent")
    server.add("Lists/a", 1, "invoice list")
    server.add("Elsewhere", 1, "invoice other account")
    found = [item async for item in matches(make_settings(), parse_rules(RULES), server.connect, follow=False)]
    assert sorted((item.mail.folder, item.mail.uid) for item in found) == [("INBOX", 1), ("Lists", 1), ("Lists/a", 1)]
    assert {item.rule.name for item in found} == {"unread invoices"}
    assert {item.kind for item in found} == {MatchKind.existing}
# end def


async def test_new_and_changed_mails_arrive_after_existing() -> None:
    server = FakeServer()
    server.add("INBOX", 1, "invoice first")
    generator = matches(make_settings(), parse_rules(RULES), server.connect)
    [first] = await take(generator, 1)
    assert (first.kind, first.mail.uid) == (MatchKind.existing, 1)

    await asyncio.sleep(0.05)
    server.add("INBOX", 2, "another invoice")
    server.push()
    [second] = await take(generator, 1)
    assert (second.kind, second.mail.uid) == (MatchKind.new, 2)

    server.add("INBOX", 3, "irrelevant")
    server.set_flags("INBOX", 1, "\\Seen")
    server.set_flags("INBOX", 2, "")
    server.push()
    [third] = await take(generator, 1)
    assert (third.kind, third.mail.uid) == (MatchKind.changed, 2)
    await generator.aclose()
# end def


async def test_polling_without_idle_finds_new_mails() -> None:
    server = FakeServer(capabilities={"IMAP4REV1"})
    server.add("INBOX", 1, "nothing")
    generator = matches(make_settings(), parse_rules(RULES), server.connect)
    pending = asyncio.create_task(take(generator, 1))
    await asyncio.sleep(0.05)
    server.add("INBOX", 2, "invoice via polling")
    [found] = await asyncio.wait_for(pending, 2)
    assert (found.kind, found.mail.uid) == (MatchKind.new, 2)
    await generator.aclose()
# end def


async def test_uidvalidity_change_reloads_folder() -> None:
    server = FakeServer()
    server.add("INBOX", 1, "invoice old")
    generator = matches(make_settings(), parse_rules(RULES), server.connect)
    await take(generator, 1)
    await asyncio.sleep(0.05)
    folder = server.folders["INBOX"]
    folder.uidvalidity = 2
    folder.messages.clear()
    server.add("INBOX", 1, "invoice renumbered")
    server.push()
    [reloaded] = await take(generator, 1)
    assert (reloaded.kind, reloaded.mail.headers["Subject"]) == (MatchKind.existing, "invoice renumbered")
    await generator.aclose()
# end def


async def test_failures_are_raised_to_the_consumer() -> None:
    server = FakeServer()
    server.add("INBOX", 1, "invoice")

    def broken(settings: object) -> object:
        raise RuntimeError("no route to host")
    # end def

    try:
        [item async for item in matches(make_settings(), parse_rules(RULES), broken, follow=False)]  # type: ignore[arg-type]
    except RuntimeError as error:
        assert "no route" in str(error)
    else:
        raise AssertionError("expected the failure")
    # end try
# end def


async def test_warns_when_no_rule_location_matches_the_account(caplog: pytest.LogCaptureFixture) -> None:
    rules = parse_rules(f"rules:\n  - name: foreign\n    locations: [{{account_id: {OTHER}}}]\n    when: {{type: bool, field: seen}}\n")
    with caplog.at_level(logging.WARNING):
        found = [item async for item in matches(make_settings(), rules, FakeServer().connect, follow=False)]
    assert found == []
    assert "No folder to watch" in caplog.text
    assert str(OTHER) in caplog.text
# end def
