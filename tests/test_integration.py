"""Talks to a real server. Skipped unless the `TEST_IMAP_*` variables are set (use a throwaway mailbox)."""

import os
from uuid import uuid4

import pytest

from remote_imap_mail_rules.imap.client import ImapClient

from .settings import TestImapSettings

pytestmark = pytest.mark.skipif("TEST_IMAP_HOST" not in os.environ, reason="TEST_IMAP_* not set")


async def test_inbox_pages_and_state() -> None:
    settings = TestImapSettings(imap_account_id=os.environ.get("TEST_IMAP_ACCOUNT_ID", str(uuid4())))  # type: ignore[call-arg]
    async with ImapClient(settings) as client:
        state = await client.examine("INBOX")
        assert state.uidvalidity > 0
        async for page in client.iter_pages(settings.imap_account_id, "INBOX", settings.imap_page_size):
            assert len(page) <= settings.imap_page_size
            assert page == sorted(page, key=lambda mail: mail.uid, reverse=True)
            break
        # end for
    # end with
# end def
