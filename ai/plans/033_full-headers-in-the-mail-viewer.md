# Full headers in the mail viewer

## Context

Todo `3bc42369`: "in the mail viewer allow to see the full headers of a email".
`GET /api/mail/accounts/{id}/messages/{uid}` already returns every header as `headers: [{name, value}]` (`server/mail_view.py:118`) and `Detail.headers` is typed in `frontend/src/model/mail-api.ts`.
Only the UI is missing, so this is a frontend-only change.

## Changes

- `frontend/src/components/MailMessage.vue`: below the `<dl class="meta">`, add a `<details class="all-headers">` with the summary `All headers (n)`.
  Inside, a `<dl>` listing each header name and value in the order the server sent them (repeated names such as `Received` stay separate rows).
  Values keep their line breaks and wrap (`white-space: pre-wrap; overflow-wrap: anywhere`).
  The element is closed by default and shown in the compact side panel too, since it needs no toolbar.
  It closes again when another mail opens, by keying it on `store.detail.uid`.
- `frontend/src/styles/main.scss`: style `.all-headers` next to `.blocked-images` (same margin, border, radius), name column in the muted colour, monospace values.
- Tests: add a case to `frontend/e2e/mail.spec.ts` that opens a mail, expands "All headers" and checks that a header from `e2e/mail-mock.ts` (`headers` at line 47) is visible, and that it is collapsed by default.
  Run on both Chromium and `webkit-ipad`.
- `CLAUDE.md`: add one sentence about the `All headers` disclosure to the mail view paragraph.

## Verification

`cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`, plus `uv run pytest` (nothing in the backend changes).
Then close the todo: tick the checkbox in `ai/todo.md`; the CalDAV completion and sync are skipped because this run is "without sync or MCP", so report that they are pending.
