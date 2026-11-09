# Plan: Stop reporting the contentless "Non-Error promise rejection ... undefined" browser event (REMOTE-IMAP-MAIL-RULES-VUE-1)

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

Todo `3c2db7b4-c683-46bc-ba31-08c320ffbba3`, Bugsink issue `bd6962e8-299b-4837-8463-8f851fbb3930`.

## Context

REMOTE-IMAP-MAIL-RULES-VUE-1 is an `UnhandledRejection`, "Non-Error promise rejection captured with value: undefined", mechanism `auto.browser.global_handlers.onunhandledrejection`.
There are two events, both from Safari 27 on macOS, 2026-11-05 (releases `0139e1b1` and `f47bcb3a`), on `/mail/<account>/INBOX/31270` and on `/rules/1`.
Neither has a stack trace, and the breadcrumbs show no request or click close to the event: it fired 4 and 17 minutes after the last breadcrumb, while the page was idle.

The frontend has no code that can reject with `undefined`.
There is no `Promise.reject`, `new Promise`, `AbortController` or `throw undefined`, every `navigator.clipboard` call sits in a `try`/`catch`, the fetch clients throw `ApiError` or let fetch's own `TypeError` through, and `router.push` calls are `void`-ed but resolve with a failure object instead of rejecting.
So the rejection comes from outside the app code (a Safari extension or WebKit itself) and nothing can be fixed at the source.
It is the same kind of non-actionable noise as the login failures that were already kept out of Sentry.

## Approach

Drop exactly this event in the Sentry init, and keep reporting every real `Error` rejection.

- `frontend/src/sentry.ts`: export a constant `IGNORED_ERRORS = [/^Non-Error promise rejection captured with value: undefined$/]` with a comment saying why (no stack, no source in the app, idle page, Safari), and pass it as `ignoreErrors` in `initSentry`.
- Rejections with another non-Error value (a string, an object) stay reported, since those carry a value that may point at the source.
- `CLAUDE.md`: one sentence in the "Error reporting" decision that the frontend ignores the valueless non-Error rejection and why.

## Tests

- `frontend/src/__tests__/sentry.spec.ts`: extend "starts with the config" to check `ignoreErrors` is passed, and add a test that the pattern matches the exact message from Bugsink and does not match "Non-Error promise rejection captured with value: boom" or a normal `Error` message.

## Verification

- `cd frontend && yarn test`, `yarn lint`, `yarn build`, then `uv run pytest` from the root for the full suite.
- After the deploy, the Bugsink issue gets no new events from that message; resolving the issue is left to the user.
