import hashlib

import pytest

from remote_imap_mail_rules.demo import mask_addresses, mask_email, mask_title, parse_args
from remote_imap_mail_rules.matching import matches
from remote_imap_mail_rules.mail import Mail
from remote_imap_mail_rules.rules.loader import parse_rules

from .fake_imap import FakeServer
from .test_imap import ACCOUNT, make_settings


def test_mask_email() -> None:
    assert mask_email("mike@example.com") == "m…e@e…e.com"
    assert mask_email("a@b.org") == "a@b.org"
    assert mask_email("john.doe@mail.example.co.uk") == "j…e@m…o.uk"
# end def


def test_mask_email_multi_label_domain() -> None:
    assert mask_email("mike@mail.example.com") == "m…e@m…e.com"
# end def


def test_mask_addresses_drops_display_names() -> None:
    assert mask_addresses('"Mike Doe" <mike@example.com>, other@example.org') == "m…e@e…e.com, o…r@e…e.org"
# end def


def test_mask_title_is_md5() -> None:
    assert mask_title("Invoice") == hashlib.md5(b"Invoice").hexdigest()
# end def


def test_streamer_flag_required_when_not_interactive(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as error:
        parse_args([], interactive=False)
    # end with
    assert error.value.code == 2
    assert "--streamer-mode" in capsys.readouterr().err
# end def


def test_streamer_flag_choices() -> None:
    assert parse_args(["--streamer-mode"], interactive=False).streamer_mode is True
    assert parse_args(["--no-streamer-mode"], interactive=False).streamer_mode is False
    assert parse_args([], interactive=True).streamer_mode is False
    assert parse_args(["--verbose"], interactive=True).verbose is True
# end def


async def test_on_inspect_sees_every_mail_once() -> None:
    server = FakeServer()
    server.add("INBOX", 1, "invoice")
    server.add("INBOX", 2, "hello")
    rules = parse_rules(
        f"""
rules:
  - name: invoices
    locations: [{{account_id: {ACCOUNT}}}]
    when: {{type: text, field: subject, operator: contains, value: invoice}}
"""
    )
    seen: list[Mail] = []
    found = [item async for item in matches(make_settings(), rules, server.connect, follow=False, on_inspect=seen.append)]
    assert [item.mail.uid for item in found] == [1]
    assert sorted(mail.uid for mail in seen) == [1, 2]
# end def
