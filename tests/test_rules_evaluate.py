import pytest
import yaml
from pydantic import TypeAdapter

from remote_imap_mail_rules.mail import Mail
from remote_imap_mail_rules.rules.evaluate import evaluate
from remote_imap_mail_rules.rules.models import Expression

from .conftest import NOW, make_mail

adapter = TypeAdapter(Expression)


def build(raw: str | None = None, **overrides: object) -> Mail:
    return make_mail(raw, **overrides) if raw is not None else make_mail(**overrides)
# end def


async def check(source: str, expected: bool, **overrides: object) -> None:
    expression = adapter.validate_python(yaml.safe_load(source))
    assert await evaluate(expression, build(**overrides), NOW) is expected, source
# end def


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("{type: text, field: subject, operator: contains, value: newsletter}", True),
        ("{type: text, field: subject, operator: contains, value: newsletter, case_sensitive: true}", False),
        ("{type: text, field: subject, operator: contains, value: 'über'}", True),
        ("{type: text, field: subject, operator: startswith, value: weekly}", True),
        ("{type: text, field: subject, operator: endswith, value: CATS}", True),
        ("{type: text, field: subject, operator: endswith, value: CATS, case_sensitive: true}", False),
        ("{type: text, field: subject, operator: equals, value: nope}", False),
        ("{type: text, field: subject, operator: regex, value: 'NEWS\\w+'}", True),
        ("{type: text, field: subject, operator: regex, value: 'NEWS\\w+', case_sensitive: true}", False),
        ("{type: text, field: subject, operator: glob, value: 'weekly *'}", True),
        ("{type: text, field: folder, operator: in, value: [inbox, spam]}", True),
        ("{type: text, field: folder, operator: in, value: [inbox], case_sensitive: true}", False),
        ("{type: text, field: auth_spf, operator: equals, value: pass}", True),
        ("{type: text, field: auth_dkim, operator: equals, value: pass}", False),
        ("{type: text, field: keywords, operator: equals, value: $important}", True),
        ("{type: text, field: attachment_extension, operator: equals, value: pdf}", True),
        ("{type: text, field: attachment_filename, operator: startswith, value: invoice}", True),
        ("{type: text, field: attachment_mime_type, operator: equals, value: image/png, quantifier: all}", False),
        ("{type: text, field: attachment_mime_type, operator: startswith, value: 'image', quantifier: none}", False),
        ("{type: text, field: body_text, operator: contains, value: world}", True),
        ("{type: text, field: body_html, operator: contains, value: world}", False),
        ("{type: text, field: list_id, operator: contains, value: x}", False),
        ("{type: header, name: x-custom, operator: equals, value: HELLO}", True),
        ("{type: header, name: x-missing, operator: equals, value: x}", False),
    ],
)
async def test_text(source: str, expected: bool) -> None:
    await check(source, expected)
# end def


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("{type: address, field: from, operator: equals, value: m.muster@example.com}", True),
        ("{type: address, field: from, part: name, operator: equals, value: max mustermann}", True),
        ("{type: address, field: from, part: full, operator: equals, value: 'Max Mustermann <m.muster@example.com>'}", True),
        ("{type: address, field: from, part: domain, operator: equals, value: example.com}", True),
        ("{type: address, field: from, part: local_part, operator: equals, value: m.muster}", True),
        ("{type: address, field: to, part: domain, operator: equals, value: example.net}", True),
        ("{type: address, field: to, part: domain, operator: equals, value: example.net, quantifier: all}", False),
        ("{type: address, field: recipients, part: domain, operator: in, value: [example.net, example.org], quantifier: all}", True),
        ("{type: address, field: cc, operator: equals, value: carol@example.net}", True),
        ("{type: address, field: reply_to, operator: contains, value: x}", False),
    ],
)
async def test_address(source: str, expected: bool) -> None:
    await check(source, expected)
# end def


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("{type: number, field: size, operator: eq, value: 2048}", True),
        ("{type: number, field: size, operator: ne, value: 2048}", False),
        ("{type: number, field: size, operator: lt, value: 2049}", True),
        ("{type: number, field: size, operator: gt, value: 2048}", False),
        ("{type: number, field: size, operator: gte, value: 2048}", True),
        ("{type: number, field: size, operator: lte, value: 2047}", False),
        ("{type: number, field: size, operator: between, value: [2000, 2048]}", True),
        ("{type: number, field: spam_score, operator: gte, value: 5}", True),
        ("{type: number, field: attachments_count, operator: eq, value: 2}", True),
        ("{type: number, field: attachment_size, operator: gt, value: 500, quantifier: all}", False),
        ("{type: number, field: attachment_size, operator: gt, value: 500}", True),
        ("{type: number, field: modseq, operator: gt, value: 0}", False),
    ],
)
async def test_number(source: str, expected: bool) -> None:
    await check(source, expected)
# end def


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("{type: date, field: date_sent, operator: lt, value: {relative: true, value: 7d}}", True),
        ("{type: date, field: date_sent, operator: lt, value: {relative: true, value: 8d}}", False),
        ("{type: date, field: date_received, operator: gt, value: {relative: false, value: '2026-10-26T08:00:00+00:00'}}", True),
        ("{type: date, field: date_sent, operator: eq, value: {relative: false, value: '2026-10-26T08:00:00'}}", True),
        ("{type: date, field: date_sent, operator: between, value: [{relative: true, value: 30d}, {relative: true, value: 1d}]}", True),
        ("{type: date, field: date_sent, operator: between, value: [{relative: true, value: 3d}, {relative: true, value: 1d}]}", False),
    ],
)
async def test_date(source: str, expected: bool) -> None:
    await check(source, expected)
# end def


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("{type: bool, field: seen}", True),
        ("{type: bool, field: seen, value: false}", False),
        ("{type: bool, field: flagged}", False),
        ("{type: bool, field: flagged, value: false}", True),
        ("{type: bool, field: has_list_unsubscribe}", True),
        ("{type: bool, field: is_reply}", False),
        ("{type: bool, field: spam_flag, value: false}", True),
        ("{type: bool, field: attachment_inline, quantifier: all}", False),
        ("{type: bool, field: attachment_inline}", True),
    ],
)
async def test_bool(source: str, expected: bool) -> None:
    await check(source, expected)
# end def


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("{type: presence, field: list_id}", False),
        ("{type: presence, field: list_id, value: false}", True),
        ("{type: presence, field: subject}", True),
        ("{type: presence, header: X-Custom}", True),
        ("{type: presence, header: X-Empty, operator: empty}", True),
        ("{type: presence, header: X-Custom, operator: empty}", False),
        ("{type: presence, header: X-Custom, operator: empty, value: false}", True),
        ("{type: presence, header: X-Nope, operator: empty}", False),
        ("{type: presence, field: body_html}", False),
        ("{type: presence, field: body_text}", True),
    ],
)
async def test_presence(source: str, expected: bool) -> None:
    await check(source, expected)
# end def


async def test_combinators() -> None:
    true = "{type: bool, field: seen}"
    false = "{type: bool, field: flagged}"
    await check(f"{{type: all, conditions: [{true}, {true}]}}", True)
    await check(f"{{type: all, conditions: [{true}, {false}]}}", False)
    await check(f"{{type: any, conditions: [{false}, {true}]}}", True)
    await check(f"{{type: any, conditions: [{false}, {false}]}}", False)
    await check(f"{{type: not, condition: {false}}}", True)
    await check(f"{{type: not, condition: {{type: any, conditions: [{false}, {true}]}}}}", False)
    await check(f"{{type: any, conditions: [{false}, {{type: all, conditions: [{true}, {{type: not, condition: {false}}}]}}]}}", True)
# end def


async def test_missing_field_is_false_even_for_negating_operators() -> None:
    bare = "Subject: x\n\nbody\n"
    await check("{type: number, field: spam_score, operator: ne, value: 1}", False, raw=bare)
    await check("{type: text, field: list_id, operator: regex, value: '^(?!x)'}", False, raw=bare)
    await check("{type: address, field: from, operator: contains, value: x, quantifier: none}", False, raw=bare)
# end def


async def test_bodies_load_lazily_once() -> None:
    from remote_imap_mail_rules.mail import Bodies

    calls = 0

    async def load() -> Bodies:
        nonlocal calls
        calls += 1
        return Bodies(text="x")
    # end def

    mail = make_mail(body_loader=load)
    expression = adapter.validate_python({"type": "bool", "field": "seen"})
    await evaluate(expression, mail, NOW)
    assert calls == 0
    body = adapter.validate_python({"type": "text", "field": "body_text", "operator": "equals", "value": "x"})
    await evaluate(body, mail, NOW)
    await evaluate(body, mail, NOW)
    assert calls == 1
# end def
