"""Prints every mail matching the rules, the existing ones first, then new ones as they arrive.

    uv run python -m remote_imap_mail_rules.demo
"""

import asyncio
import logging

from .config import ImapSettings
from .matching import matches
from .rules.loader import load_rules


async def main() -> None:
    settings = ImapSettings()  # type: ignore[call-arg]  # filled from the environment / .env
    rule_file = load_rules(settings.rules_path)
    print(f"{len(rule_file.rules)} rules from {settings.rules_path}, watching account {settings.imap_account_name or settings.imap_account_id}")
    async for found in matches(settings, rule_file):
        mail = found.mail
        print(f"[{found.kind}] {found.rule.name!r}: {mail.folder} #{mail.uid} from={mail.headers.get('From')} subject={mail.headers.get('Subject')!r}")
    # end for
# end def


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    # end try
# end if
