# Plan: Ignore the `undefined` promise rejection in the frontend error reporting

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

## Context

Todo `3c2db7b4`, Bugsink REMOTE-IMAP-MAIL-RULES-VUE-1: `UnhandledRejection`, "Non-Error promise rejection captured with value: undefined".
Two events, 2026-11-05, both on `/rules/1` in Safari 27, mechanism `onunhandledrejection`, no stack trace.

Findings:

- The breadcrumbs show only `/api/dry-run` fetches (200) and clicks.
  No user action or failing request precedes the error by seconds, so nothing points at a first-party code path.
- The frontend has no `reject()`, `abort()`, `AbortController`, `Promise.reject` or `new Promise`.
  Every `navigator.clipboard` call is inside `try` / `catch`.
  `DryRunPanel.fetchPages` catches all errors.
- A rejection with `undefined` and no stack is typical of browser internals or extensions (Safari, password managers).
  It carries no information to act on, so it is noise in Bugsink.

## Change

`frontend/src/sentry.ts`, `initSentry`: add `ignoreErrors: [/^Non-Error promise rejection captured with value: undefined$/]` to `Sentry.init`.
Only this exact message is dropped.
Rejections with other values, or real `Error`s, are still reported.
A short comment names why (no stack, no first-party source found, ticket REMOTE-IMAP-MAIL-RULES-VUE-1).

## Tests

`frontend/src/__tests__/sentry.spec.ts`: the init call receives `ignoreErrors` matching the `undefined` message and not `... with value: "boom"` or other messages.

## Docs

`CLAUDE.md` error reporting bullet: one sentence that the frontend ignores the valueless non-Error rejection.

## Verification

`cd frontend && yarn test && yarn lint && yarn build`, then `uv run pytest` for the whole suite.
After a deploy, mark the Bugsink issue resolved if it does not return.
