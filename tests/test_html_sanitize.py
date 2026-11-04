"""The mail HTML sanitizer: remote content is blocked and reported, embedded images and cid parts work."""

from remote_imap_mail_rules.server.html_sanitize import sanitize_html


def parts(content_id: str) -> str | None:
    return "/part/1" if content_id.lower() == "logo@x" else None
# end def


def test_scripts_and_handlers_never_survive() -> None:
    out = sanitize_html('<p onclick="x()">a</p><script>alert(1)</script><a href="javascript:x()">b</a>', parts, True, True)
    assert "<script" not in out.html and "onclick" not in out.html and "javascript" not in out.html
# end def


def test_cid_images_use_the_part_url_case_insensitively() -> None:
    out = sanitize_html('<img src="cid:LOGO@x" alt="logo"><img src="cid:gone@x" alt="gone">', parts)
    assert 'src="/part/1"' in out.html
    assert out.broken_embeds == ["cid:gone@x"]
    assert out.blocked_images == []
# end def


def test_remote_images_are_blocked_and_listed() -> None:
    out = sanitize_html('<img src="https://t.example/a.gif" alt="a"><img src="https://t.example/a.gif"><img src="http://x.example/b.png">', parts)
    assert "t.example" not in out.html
    assert out.blocked_images == ["https://t.example/a.gif", "http://x.example/b.png"]
# end def


def test_remote_images_when_allowed_get_no_referrer() -> None:
    out = sanitize_html('<img src="https://t.example/a.gif" alt="a">', parts, allow_remote=True)
    assert 'src="https://t.example/a.gif"' in out.html
    assert 'referrerpolicy="no-referrer"' in out.html
    assert out.blocked_images == []
# end def


def test_embedded_images_pass_but_not_other_data_urls() -> None:
    out = sanitize_html('<img src="data:image/png;base64,AAAA"><img src="data:text/html;base64,AAAA"><a href="data:text/html,x">x</a>', parts, True)
    assert out.html.count("data:image/png") == 1
    assert "text/html" not in out.html
# end def


def test_styles_are_left_out_by_default() -> None:
    out = sanitize_html('<style>p{color:red}</style><p style="color:blue">x</p>', parts)
    assert "<style" not in out.html and "style=" not in out.html
    assert out.styles_blocked
# end def


def test_allowed_styles_are_filtered() -> None:
    css = '@import url(https://x.example/a.css);p{color:red;position:fixed;background:url(https://t.example/b.png)}q{background:url(cid:logo@x)}'
    out = sanitize_html(f'<style>{css}</style><p style="width:expression(alert(1))">x</p>', parts, allow_styles=True)
    assert "color:red" in out.html
    assert "@import" not in out.html and "fixed" not in out.html and "expression(" not in out.html
    assert "t.example" not in out.html and 'url("/part/1")' in out.html
    assert out.blocked_images == ["https://t.example/b.png"]
# end def
