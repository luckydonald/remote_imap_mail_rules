"""Makes the HTML of a mail safe to show: no scripts or event handlers, `cid:` images pointing at our own parts.

Remote images and mail styles are blocked on purpose (a remote image tells the sender that and when the mail was read), and every blocked
remote URL is reported so the reader can see what was left out and allow it. The viewer adds a content security policy on top, this is the first layer.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass, field

import nh3

TAGS = set(nh3.ALLOWED_TAGS) | {"img"}
ATTRIBUTES = {tag: set(attributes) for tag, attributes in nh3.ALLOWED_ATTRIBUTES.items()}
ATTRIBUTES["img"] = {"src", "alt", "width", "height"}
# `cid` and `data` have to pass the scheme check so that `keep` can decide on `img src`; `keep` refuses them everywhere else.
URL_SCHEMES = {"http", "https", "mailto", "cid", "data"}
EMBEDDED_IMAGE = re.compile(r"^data:image/(png|jpeg|gif|webp)[;,]", re.IGNORECASE)
STYLE_BLOCK = re.compile(r"<style\b[^>]*>(.*?)</style\s*>", re.IGNORECASE | re.DOTALL)
CSS_URL = re.compile(r"""url\(\s*(['"]?)(.*?)\1\s*\)""", re.IGNORECASE | re.DOTALL)
CSS_IMPORT = re.compile(r"@import\b[^;{]*;?", re.IGNORECASE)
CSS_DANGEROUS = re.compile(r"expression\s*\(|behaviou?r\s*:|-moz-binding\s*:|javascript:", re.IGNORECASE)
CSS_POSITION = re.compile(r"position\s*:\s*(fixed|sticky)", re.IGNORECASE)


@dataclass
class Sanitized:
    html: str
    #: Remote URLs that were left out (or, with `allow_remote`, none), in the order they appear, once each.
    blocked_images: list[str] = field(default_factory=list)
    #: `cid:` references without a part in the mail.
    broken_embeds: list[str] = field(default_factory=list)
    #: Whether the mail had styles that were left out.
    styles_blocked: bool = False
# end class


def add_once(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)
    # end if
# end def


def clean_css(css: str, part_url: Callable[[str], str | None], allow_remote: bool, blocked: list[str]) -> str:
    """Drops what could load something or cover the page: `@import`, scripted values, off-site `url()` (unless allowed), `position: fixed`."""
    css = css.replace("\\", "").replace("<", "").replace("/*", " ").replace("*/", " ")  # escapes and comments hide keywords from the checks below
    css = CSS_IMPORT.sub("", css)
    if CSS_DANGEROUS.search(css):
        css = CSS_DANGEROUS.sub("invalid-", css)
    # end if
    css = CSS_POSITION.sub("position:static", css)

    def replace(match: re.Match[str]) -> str:
        value = match.group(2).strip()
        if value.lower().startswith("cid:"):
            url = part_url(value[4:].strip("<>"))
            return f'url("{url}")' if url else "none"
        # end if
        if EMBEDDED_IMAGE.match(value):
            return match.group(0)
        # end if
        if value.lower().startswith(("http://", "https://")):
            if allow_remote:
                return f'url("{value}")'
            # end if
            add_once(blocked, value)
        # end if
        return "none"
    # end def

    return CSS_URL.sub(replace, css)
# end def


def sanitize_html(
    html: str, part_url: Callable[[str], str | None], allow_remote: bool = False, allow_styles: bool = False
) -> Sanitized:
    """`part_url` maps a `Content-ID` to the URL of that part, or `None` when the mail has no such part."""
    result = Sanitized(html="")
    styles: list[str] = []

    def take_style(match: re.Match[str]) -> str:
        if allow_styles:
            styles.append(clean_css(match.group(1), part_url, allow_remote, result.blocked_images))
        elif match.group(1).strip():
            result.styles_blocked = True
        # end if
        return ""
    # end def

    html = STYLE_BLOCK.sub(take_style, html)

    def keep(tag: str, attribute: str, value: str) -> str | None:
        if attribute == "style":
            if not allow_styles:
                result.styles_blocked = True
                return None
            # end if
            return clean_css(value, part_url, allow_remote, result.blocked_images)
        # end if
        lowered = value.strip().lower()
        if tag == "img" and attribute == "src":
            if lowered.startswith("cid:"):
                url = part_url(value.strip()[4:].strip("<>"))
                if url is None:
                    add_once(result.broken_embeds, value.strip())
                # end if
                return url
            # end if
            if EMBEDDED_IMAGE.match(value.strip()):
                return value.strip()
            # end if
            if lowered.startswith(("http://", "https://")):
                if allow_remote:
                    return value.strip()
                # end if
                add_once(result.blocked_images, value.strip())
            # end if
            return None
        # end if
        if lowered.startswith(("cid:", "data:")):
            return None  # only images may use these
        # end if
        return value
    # end def

    attributes = {tag: set(names) for tag, names in ATTRIBUTES.items()}
    if allow_styles:
        attributes.setdefault("*", set()).add("style")
    # end if
    cleaned = nh3.clean(
        html,
        tags=TAGS,
        attributes=attributes,
        url_schemes=URL_SCHEMES,
        attribute_filter=keep,
        set_tag_attribute_values={"img": {"referrerpolicy": "no-referrer", "loading": "lazy"}},
    )
    prefix = "".join(f"<style>{css}</style>" for css in styles if css.strip())
    result.html = prefix + cleaned
    return result
# end def
