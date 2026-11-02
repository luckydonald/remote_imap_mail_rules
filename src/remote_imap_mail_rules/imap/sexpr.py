"""Tokenizer and parser for the parenthesized lists of IMAP responses (FETCH data, BODYSTRUCTURE, LIST)."""

import re

Chunk = bytes | bytearray
Node = str | bytes | None | list["Node"]

TOKEN_RE = re.compile(rb'\s*(?:(\()|(\))|"((?:[^"\\]|\\.)*)"|(\{\d+\}$)|([^\s()"{]+))')
LITERAL_RE = re.compile(rb"\{(\d+)\}$")


def tokenize(chunks: list[Chunk]) -> list[bytes | bytearray | str]:
    """Splits response chunks into tokens.

    aioimaplib hands over text lines as `bytes` and the literal that follows a line ending in `{n}` as `bytearray`.
    Parens become `"("` / `")"`, atoms and quoted strings become `bytes`, literals stay `bytearray`.
    """
    tokens: list[bytes | bytearray | str] = []
    for chunk in chunks:
        if isinstance(chunk, bytearray):
            tokens.append(chunk)
            continue
        # end if
        position = 0
        while position < len(chunk):
            match = TOKEN_RE.match(chunk, position)
            if match is None:
                break
            # end if
            position = match.end()
            open_, close, quoted, literal_marker, atom = match.groups()
            if open_:
                tokens.append("(")
            elif close:
                tokens.append(")")
            elif quoted is not None:
                tokens.append(re.sub(rb"\\(.)", rb"\1", quoted))
            elif literal_marker:
                continue
            elif atom is not None:
                tokens.append(atom)
            # end if
        # end while
    # end for
    return tokens
# end def


def parse(chunks: list[Chunk]) -> list[Node]:
    """Parses chunks into nested lists. Atoms and strings are `str`, literals `bytes`, `NIL` is `None`."""
    tokens = tokenize(chunks)
    stack: list[list[Node]] = [[]]
    for token in tokens:
        if token == "(":
            stack.append([])
            continue
        # end if
        if token == ")":
            if len(stack) == 1:
                continue
            # end if
            finished = stack.pop()
            stack[-1].append(finished)
            continue
        # end if
        if isinstance(token, bytearray):
            stack[-1].append(bytes(token))
            continue
        # end if
        assert isinstance(token, bytes)
        text = token.decode("utf-8", errors="replace")
        stack[-1].append(None if text.upper() == "NIL" else text)
    # end for
    while len(stack) > 1:
        finished = stack.pop()
        stack[-1].append(finished)
    # end while
    return stack[0]
# end def
