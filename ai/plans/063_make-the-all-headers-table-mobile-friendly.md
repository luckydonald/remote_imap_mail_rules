# Make the "All headers" table mobile friendly

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

## Context

Todo `526faa83-2054-43f2-99f4-6beb7c7a3902`: the `All headers (n)` disclosure of the mail view (`frontend/src/components/MailMessage.vue:111`) is a `<dl>` styled as a two column grid in `.all-headers` (`frontend/src/styles/main.scss`, around line 1535).
The grid is `max-content 1fr`, so on a small screen a long header name (`X-Google-DKIM-Signature`, `ARC-Authentication-Results`) takes as much width as it wants and squeezes the value column, and long unbroken values can push the grid wider than the screen.
The mail view is also used in the narrow side panel of the editor, where the same problem shows.

## Findings

- Only markup is a `dl` with `dt` (name) and `dd` (value) pairs, no component of its own, so the fix is CSS only.
- The sibling `@media (width < 700px)` block at `main.scss:1440` is the project's phone breakpoint.
- The existing e2e test `lists all headers of a message, collapsed at first` in `frontend/e2e/mail.spec.ts:50` checks `dt` / `dd` and must keep passing.

## Changes

1. `frontend/src/styles/main.scss`, `.all-headers`:
   - Make the grid `minmax(0, max-content) minmax(0, 1fr)`-safe: use `grid-template-columns: minmax(0, max-content) minmax(0, 1fr)` and `overflow-wrap: anywhere` on `dt`, so nothing can widen the box.
   - Under `@media (width < 700px)` switch the `dl` to a single column: the name sits above its value, the name is small and muted, with a little space and a thin divider between header entries.
2. `frontend/e2e/mail.spec.ts`: new test with a phone viewport (`page.setViewportSize({ width: 375, height: 700 })`) that opens the headers and checks that the `dl` has no horizontal overflow (`scrollWidth <= clientWidth`) and that a `dd` sits below its `dt` (bounding box of the `dd` has `y` greater than the `dt`'s), using a long header name and a long unbroken value in the mock data.
3. No `CLAUDE.md` change needed beyond one short clause in the "Mail view" paragraph: `All headers (n)` stacks name over value under 700 px.

## Verification

- `cd frontend && yarn test:e2e e2e/mail.spec.ts` (both Chromium and `webkit-ipad`), `yarn test`, `yarn lint`, `yarn build`.
- `uv run pytest` once, since the repo rule is to run the full suite.
