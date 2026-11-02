"""Reads BODYSTRUCTURE into a flat list of parts, to find attachments and the text parts to download."""

from dataclasses import dataclass, field

from .sexpr import Node


@dataclass(frozen=True)
class Part:
    number: str
    mime_type: str
    params: dict[str, str] = field(default_factory=dict)
    encoding: str = "7bit"
    size: int | None = None
    disposition: str | None = None
    filename: str | None = None

    @property
    def is_attachment(self) -> bool:
        if self.mime_type.startswith("multipart/"):
            return False
        # end if
        return self.disposition == "attachment" or bool(self.filename)
    # end def

    @property
    def inline(self) -> bool:
        return self.disposition == "inline"
    # end def
# end class


def params_dict(node: Node) -> dict[str, str]:
    if not isinstance(node, list):
        return {}
    # end if
    pairs = zip(node[::2], node[1::2], strict=False)
    return {key.lower(): value for key, value in pairs if isinstance(key, str) and isinstance(value, str)}
# end def


def as_int(node: Node) -> int | None:
    if isinstance(node, str) and node.isdigit():
        return int(node)
    # end if
    return None
# end def


def basic_part(node: list[Node], number: str) -> Part | None:
    if len(node) < 7 or not isinstance(node[0], str) or not isinstance(node[1], str):
        return None
    # end if
    mime_type = f"{node[0]}/{node[1]}".lower()
    params = params_dict(node[2])
    if mime_type == "message/rfc822":
        disposition_index = 11
    elif node[0].lower() == "text":
        disposition_index = 9
    else:
        disposition_index = 8
    # end if
    disposition: str | None = None
    disposition_params: dict[str, str] = {}
    if len(node) > disposition_index and isinstance(node[disposition_index], list):
        raw = node[disposition_index]
        assert isinstance(raw, list)
        if raw and isinstance(raw[0], str):
            disposition = raw[0].lower()
        # end if
        disposition_params = params_dict(raw[1]) if len(raw) > 1 else {}
    # end if
    return Part(
        number=number,
        mime_type=mime_type,
        params=params,
        encoding=(node[5] or "7bit").lower() if isinstance(node[5], str) else "7bit",
        size=as_int(node[6]),
        disposition=disposition,
        filename=disposition_params.get("filename") or params.get("name"),
    )
# end def


def walk(node: list[Node], number: str, parts: list[Part]) -> None:
    if node and isinstance(node[0], list):
        children = [child for child in node if isinstance(child, list)]
        subtype = next((item for item in node if isinstance(item, str)), "mixed")
        parts.append(Part(number=number or "0", mime_type=f"multipart/{subtype}".lower()))
        for index, child in enumerate(children, start=1):
            walk(child, f"{number}.{index}" if number else str(index), parts)
        # end for
        return
    # end if
    part = basic_part(node, number or "1")
    if part is not None:
        parts.append(part)
    # end if
# end def


def parse_parts(structure: Node) -> list[Part]:
    """All parts of a BODYSTRUCTURE value, depth first. A single-part mail is part `1`."""
    parts: list[Part] = []
    if isinstance(structure, list):
        walk(structure, "", parts)
    # end if
    return parts
# end def
