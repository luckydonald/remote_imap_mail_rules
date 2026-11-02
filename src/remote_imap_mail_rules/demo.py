"""Prints every mail matching the rules, the existing ones first, then new ones as they arrive.

    uv run python -m remote_imap_mail_rules.demo [--verbose] [--streamer-mode | --no-streamer-mode]

`--verbose` sets the log level to DEBUG (the RULES_PATH, the IMAP protocol, inspected and queued folders) and also lists every mail that gets inspected, matching or not.
`--streamer-mode` hides personal data: titles become their md5 hash and email addresses are reduced to first and last characters.
Without a terminal (agent runs, pipes) one of `--streamer-mode` / `--no-streamer-mode` is required.
"""

import argparse
import asyncio
import hashlib
import logging
import sys
from collections.abc import Sequence
from email.utils import getaddresses

from .config import ImapSettings
from .mail import Mail
from .matching import matches
from .rules.loader import load_rules

logger = logging.getLogger(__name__)

ELLIPSIS = "…"


def mask_part(part: str) -> str:
    """`mike` → `m…e`; one character or empty stays as it is."""
    if len(part) < 2:
        return part
    # end if
    return f"{part[0]}{ELLIPSIS}{part[-1]}"
# end def


def mask_email(address: str) -> str:
    """`mike@mail.example.com` → `m…e@m…e.com`: first and last character of the user and of the domain, the last label (TLD) is kept."""
    local, separator, domain = address.rpartition("@")
    if not separator:
        return mask_part(address)
    # end if
    name, dot, tld = domain.rpartition(".")
    masked_domain = f"{mask_part(name)}.{tld}" if dot else mask_part(domain)
    return f"{mask_part(local)}@{masked_domain}"
# end def


def mask_title(title: str) -> str:
    return hashlib.md5(title.encode("utf-8", errors="replace")).hexdigest()
# end def


def mask_addresses(header: str) -> str:
    """Only the masked addresses of an address header, display names are dropped as they identify people too."""
    return ", ".join(mask_email(address) for _name, address in getaddresses([header]) if address)
# end def


def describe_from(mail: Mail, streamer_mode: bool) -> str:
    value = str(mail.headers.get("From") or "")
    return mask_addresses(value) if streamer_mode else value
# end def


def describe_title(mail: Mail, streamer_mode: bool) -> str:
    value = str(mail.headers.get("Subject") or "")
    return mask_title(value) if streamer_mode else value
# end def


def is_interactive() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()
# end def


def parse_args(argv: Sequence[str] | None = None, interactive: bool | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="remote_imap_mail_rules.demo", description="Print the mails matching the rules.")
    parser.add_argument("--verbose", action="store_true", help="also list every inspected mail: account, folder, uid and title")
    parser.add_argument(
        "--streamer-mode",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="hash titles and shorten email addresses to first and last character; required (either way) when not run in a terminal",
    )
    args = parser.parse_args(argv)
    if args.streamer_mode is None:
        if not (is_interactive() if interactive is None else interactive):
            parser.error("not running in a terminal: pass either --streamer-mode or --no-streamer-mode")
        # end if
        args.streamer_mode = False
    # end if
    return args
# end def


async def main(args: argparse.Namespace) -> None:
    settings = ImapSettings()  # type: ignore[call-arg]  # filled from the environment / .env
    logger.debug("RULES_PATH=%s", settings.rules_path)
    rule_file = load_rules(settings.rules_path)
    account = settings.imap_account_name or settings.imap_account_id
    streamer_mode: bool = args.streamer_mode
    print(f"{len(rule_file.rules)} rules from {settings.rules_path}, watching account {account}")

    def on_inspect(mail: Mail) -> None:
        print(f"[inspect] account={account} folder={mail.folder} uid={mail.uid} title={describe_title(mail, streamer_mode)!r}")
    # end def

    async for found in matches(settings, rule_file, on_inspect=on_inspect if args.verbose else None):
        mail = found.mail
        print(
            f"[{found.kind}] {found.rule.name!r}: {mail.folder} #{mail.uid} from={describe_from(mail, streamer_mode)} "
            f"subject={describe_title(mail, streamer_mode)!r}"
        )
    # end for
# end def


if __name__ == "__main__":
    cli_args = parse_args()
    logging.basicConfig(level=logging.DEBUG if cli_args.verbose else logging.INFO)  # DEBUG includes the IMAP protocol of `aioimaplib`
    try:
        asyncio.run(main(cli_args))
    except KeyboardInterrupt:
        pass
    # end try
# end if
