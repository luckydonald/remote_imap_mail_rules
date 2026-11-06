# Resolve rule-style folder names in the mail browser routes

## Context

Todo `6b1a79f8` (subtask of "fix Bigsink issues"), Bugsink REMOTE-IMAP-MAIL-RULES-4 and -5.
`GET /api/mail/accounts/{id}/messages` and `.../messages/{uid}` answered 502 with `examine Boxed In/Updates failed: NO ... prefixed with: INBOX.`.
The browse routes in `server/api/mail.py` hand the `folder` query parameter straight to `EXAMINE`, so a name written like in a rule (`/` for subfolders, no `INBOX.` namespace prefix) fails on servers such as Dovecot with the `INBOX.` namespace.
Rule folders reach the browser, for example through the move targets of the rules in `MailMoveMenu.vue`, and `ImapClient.resolve_folder` already knows how to map such a name to the server's real one.

## Change

- `src/remote_imap_mail_rules/server/api/mail.py`: in the routes that take `folder` (`list_messages`, `get_message`, `get_part`, the flags route and the move route for the source folder), call `folder = await client.resolve_folder(folder)` right after the session opens.
  A name the server lists is returned unchanged, so folders from the folder list behave exactly as before.
- `MoveOut` and the move route already return the resolved target from `ImapClient.move`; no change there.
- Frontend: no change needed, the folder shown stays what the server listed; if the opened name differs from the listed one the list simply does not highlight it.
  (Checked only by reading `store/mail.ts`; no UI work planned.)

## Tests

- `tests/test_server_mail.py` (uses `FakeServer`): a fake server whose folders are `INBOX.Boxed In.Updates` with delimiter `.`; request `folder=Boxed In/Updates` for the message list and for one message and expect 200 with the mails of that folder.
  Also one case that a listed name still passes through unchanged, and that an unknown folder still gives the existing error.
- Run `uv run pytest`.

## Verification

`uv run pytest`; no frontend change, so no Playwright run. Update `CLAUDE.md` mail browser decision line: "the folder query parameter is resolved with `resolve_folder`, so rule-style names work".

## Out of scope

The 502 for a failing mail server still being reported to Sentry belongs to the other subtasks (login failed, timeouts).
