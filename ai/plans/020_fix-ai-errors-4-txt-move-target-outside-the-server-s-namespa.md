# Fix ai/errors/4.txt: move target outside the server's namespace

## Context

A rule moves a mail to `Boxed In/Updates`, and Dovecot refuses it with `Client tried to access nonexistent namespace. (Mailbox name should probably be prefixed with: INBOX.)`.
The server keeps its folders under `INBOX.` with `.` as the hierarchy delimiter, and the mail viewer shows the real name as `INBOX.Boxed in.Promotions` (the `%20` seen in the URL is only URL encoding of the space).
Rules are meant to be provider independent, and the `/` in a rule's folder means subfolder, so the client must translate a rule's folder to the server's real name.
`rules/rules.example.yml` and `rules/rules.local.yml` use `Boxed In/Updates` and `Boxed In/Promotions`.

## Approach

Add `ImapClient.resolve_folder(name) -> str` in `src/remote_imap_mail_rules/imap/client.py`, and call it for the move/copy target in `move` (line ~180) and for the folder in `append` (line ~207).
It uses the existing `list_folders` (`LIST "" *`, result cached on the client) and `FolderInfo.delimiter`:

1. If `name` equals a listed folder, return it unchanged, so names that already work and names the server sent keep working.
2. Otherwise build candidates: `name` with `/` replaced by the server delimiter, each also with the namespace prefix `INBOX` + delimiter (prefix is used only when the listed folders show that namespace, i.e. other folders start with `INBOX.`).
3. Return the first candidate that is listed, comparing exactly first and then case-insensitively (the rule says `Boxed In`, the server has `Boxed in`).
4. If nothing is listed (the target folder does not exist yet), return the delimiter-converted, prefixed candidate, so the server's own error names the real problem, and the `ImapError` message includes the resolved name.

Also use it in `expand_folder` for rule locations, so a location `Boxed In/Updates` is found the same way (today it logs "does not exist" and skips).
`VirtualWriter` (dry run) needs no change, but `ImapWriter.move` passes the raw rule folder, the resolution happens inside `ImapClient`.
Folder names stay in modified UTF-7 as sent, no decoding.

## Tests

- `tests/fake_imap.py` (`FakeServer`): allow a namespace prefix and a `.` delimiter, with folders like `INBOX.Boxed in.Updates`.
- New tests in the client tests: exact name kept, `Boxed In/Updates` resolves to `INBOX.Boxed in.Updates`, missing folder gets the prefixed guess, a server with `/` and no prefix is unchanged, `move` and `append` use the resolved name.
- Run `uv run pytest`.

## Docs

Add one line under Decisions in `CLAUDE.md`: rule folders use `/` as the hierarchy separator and are resolved to the server's namespace and delimiter by `ImapClient.resolve_folder`.

## Verification

Only `FakeServer` and `TEST_*`, never the live account.
`uv run pytest` must pass, including the new tests that reproduce the error's folder shape.
