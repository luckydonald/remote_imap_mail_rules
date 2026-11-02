from datetime import UTC, datetime
from email import message_from_string, policy
from uuid import UUID

import pytest

from remote_imap_mail_rules.mail import Attachment, Bodies, Mail

ACCOUNT_ID = UUID("6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11")
NOW = datetime(2026, 11, 2, 12, 0, tzinfo=UTC)

RAW = """From: Max Mustermann <m.muster@example.com>
To: Anna <anna@example.org>, bob@example.net
Cc: carol@example.net
Subject: Weekly Newsletter =?utf-8?q?=C3=BCber?= cats
Date: Mon, 26 Oct 2026 08:00:00 +0000
Message-ID: <abc@example.com>
List-Unsubscribe: <mailto:unsub@example.com>
X-Spam-Status: No, score=5.5 required=6.0
Authentication-Results: mx.example.org; spf=pass; dkim=fail; dmarc=pass
X-Custom: Hello
X-Empty:

body
"""


def make_mail(raw: str = RAW, **overrides: object) -> Mail:
    async def load() -> Bodies:
        return Bodies(text="Hello World", html=None)
    # end def

    values: dict[str, object] = dict(
        account_id=ACCOUNT_ID,
        folder="INBOX",
        uid=42,
        headers=message_from_string(raw, policy=policy.default),
        flags=frozenset({"\\Seen", "$Important"}),
        date_received=datetime(2026, 10, 26, 8, 1, tzinfo=UTC),
        size=2048,
        mime_type="multipart/mixed",
        attachments=[Attachment("application/pdf", "Invoice.PDF", 1000), Attachment("image/png", "logo.png", 50, inline=True)],
        body_loader=load,
    )
    values.update(overrides)
    return Mail(**values)  # type: ignore[arg-type]
# end def


@pytest.fixture
def mail() -> Mail:
    return make_mail()
# end def
