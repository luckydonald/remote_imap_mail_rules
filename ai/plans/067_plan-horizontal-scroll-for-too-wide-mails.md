# Plan: horizontal scroll for too-wide mails

Todo `4116bd36-64c6-404f-b83c-393837b6725a`, "allow vertical scroll for too-big mails". The user clarified that the problem is mails wider than the pane.

## Context

The mail body is shown in a sandboxed iframe (`.body-frame` in `MailMessage.vue`).
`fit()` only sizes the frame's height to `body.scrollHeight`, and the frame document has `html{overflow:hidden}` (`FRAME_STYLE` in `frontend/src/model/mail-format.ts`).
A mail with fixed-width content (a 600 to 1500 px table, a wide `<pre>`) is therefore clipped on the right with no way to see the rest.
Tall mails already scroll fine: Chromium and iPad WebKit were checked with 14k and 105k px mails, in the full screen view, on a phone and in the editor's side panel.

## Changes

1. `frontend/src/model/mail-format.ts`: `FRAME_STYLE` uses `html{overflow-x:auto;overflow-y:hidden}`, so the frame scrolls sideways itself and never vertically.
2. `frontend/src/components/MailMessage.vue` `fit()`: after setting the height from `body.scrollHeight`, add the height of a classic horizontal scrollbar (`frame.clientHeight - documentElement.clientHeight`, 0 for overlay scrollbars), so the bottom of the mail is not covered.
   The `ResizeObserver` observes `body`, whose size the scrollbar does not change, so there is no feedback loop.
3. `frontend/e2e/mail.spec.ts`: a test with a 1500 px wide table that checks the frame's `documentElement.scrollWidth` is larger than its `clientWidth`, that setting `scrollLeft` moves it, and that the frame still shows the whole height (no vertical scroll).
   Run it in Chromium and in the `webkit-ipad` project, which already runs this file.
4. `CLAUDE.md`: one sentence in the Mail view section, the frame scrolls sideways for wide mails and never vertically.

## Verification

- `cd frontend && yarn test && yarn test:e2e && yarn lint && yarn build`.
- `uv run pytest` is not affected (frontend only).
- Disk is nearly full (about 700 MB free), so watch for out-of-space errors.

## Commit

Scope `[frontend] mail view:`, one work commit after the rebase.
