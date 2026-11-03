"""Undoing a `Content-Transfer-Encoding` on raw part bytes, for attachments and inline images."""

import base64
import binascii
import quopri


def decode_transfer(encoding: str | None, data: bytes) -> bytes:
    """Bytes of a part after `base64` / `quoted-printable`; everything else (7bit, 8bit, binary) is already the content."""
    kind = (encoding or "").strip().lower()
    if kind == "base64":
        try:
            return base64.b64decode(data, validate=False)
        except (binascii.Error, ValueError):
            return data
        # end try
    # end if
    if kind == "quoted-printable":
        return quopri.decodestring(data)
    # end if
    return data
# end def
