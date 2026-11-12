"""Mail titles and addresses in answers, shown only to tokens with `mails:read`; others get the same masks as `demo --streamer-mode`."""

from typing import Any

from ..demo import mask_addresses, mask_title

TITLE_KEYS = {"subject", "title"}
ADDRESS_KEYS = {"from", "sender", "to", "cc", "bcc", "reply_to", "address"}


def mask_value(key: str, value: Any) -> Any:
    if isinstance(value, str):
        if key in TITLE_KEYS:
            return mask_title(value)
        # end if
        if key in ADDRESS_KEYS:
            return mask_addresses(value)
        # end if
    # end if
    return value
# end def


def redact(node: Any, key: str = "") -> Any:
    """A copy of `node` with titles hashed and addresses reduced, wherever they are by their key."""
    if isinstance(node, dict):
        return {name: redact(value, name) for name, value in node.items()}
    # end if
    if isinstance(node, list):
        return [redact(item, key) for item in node]
    # end if
    return mask_value(key, node)
# end def


def mask_message_id(message_id: str | None) -> str | None:
    return None if message_id is None else mask_title(message_id)
# end def


def mask_sender(sender: dict[str, Any]) -> dict[str, Any]:
    """The `{name, address}` of a mail summary: the display name hashed, the address reduced."""
    name = sender.get("name") or ""
    return {"name": mask_title(name) if name else "", "address": mask_addresses(sender.get("address") or "")}
# end def
