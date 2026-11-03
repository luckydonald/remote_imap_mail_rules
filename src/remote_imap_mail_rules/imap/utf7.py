"""Modified UTF-7 (RFC 3501, 5.1.3) as IMAP servers send folder names. Only used to show names, the wire name is kept as is."""

import base64
import re

SHIFTED_RE = re.compile(r"&([^-]*)-")


def decode_shifted(match: re.Match[str]) -> str:
    encoded = match.group(1)
    if not encoded:
        return "&"
    # end if
    padded = encoded.replace(",", "/")
    padded += "=" * (-len(padded) % 4)
    try:
        return base64.b64decode(padded).decode("utf-16-be")
    except (ValueError, UnicodeDecodeError):
        return match.group(0)
    # end try
# end def


def decode_folder_name(name: str) -> str:
    """`Entw&APw-rfe` becomes `Entwürfe`. Names that are no valid modified UTF-7 are returned unchanged."""
    return SHIFTED_RE.sub(decode_shifted, name)
# end def
