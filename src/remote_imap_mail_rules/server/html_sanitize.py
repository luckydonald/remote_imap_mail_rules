"""Makes the HTML of a mail safe to show: no scripts, styles or event handlers, no remote images, `cid:` images pointing at our own parts."""

from collections.abc import Callable

import nh3

TAGS = set(nh3.ALLOWED_TAGS) | {"img"}
ATTRIBUTES = {tag: set(attributes) for tag, attributes in nh3.ALLOWED_ATTRIBUTES.items()}
ATTRIBUTES["img"] = {"src", "alt", "width", "height"}
# `cid` has to pass the scheme check so that `keep` can rewrite `img src`; a `cid:` link is harmless, it points nowhere.
URL_SCHEMES = {"http", "https", "mailto", "cid"}


def sanitize_html(html: str, part_url: Callable[[str], str | None]) -> str:
    """`part_url` maps a `Content-ID` to the URL of that part, or `None` when the mail has no such part."""

    def keep(tag: str, attribute: str, value: str) -> str | None:
        if tag == "img" and attribute == "src":
            if value.lower().startswith("cid:"):
                return part_url(value[4:].strip("<>"))
            # end if
            return None  # remote images track the reader, so they are not loaded
        # end if
        return value
    # end def

    return nh3.clean(html, tags=TAGS, attributes=ATTRIBUTES, url_schemes=URL_SCHEMES, attribute_filter=keep)
# end def
