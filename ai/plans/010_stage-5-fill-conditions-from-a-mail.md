# Stage 5: fill conditions from a mail

## Context

Stage 5 of `ai/initial.md` has two open items: "filling conditions from a mail, and the fill from mail button on conditions", and the full action log per mail.
This plan covers the first item only.
The action log needs the stage 5 tables and executed actions, and is better planned separately after this lands.

Decisions from the user:
- The editor gets a collapsible side panel showing a mail. On mobile it is a subpage, like the mail browser's own pane navigation.
- The mail state moves into a shared Pinia store, cached in localStorage.
- The mail detail API is extended with headers and flags so every field type can be filled.

## Backend: extend the mail detail

- `server/mail_view.py`: add to `DetailOut` the fields `headers` (list of name/value pairs, RFC 2047 decoded), `flags`, `keywords`, `date_sent`, `date_received`, `mime_type`, `modseq`, `bcc`, `sender`, `return_path`, `delivered_to` and `attachments[].extension`.
  The data comes from the domain `Mail` (`src/remote_imap_mail_rules/mail.py:42`), reuse `addresses()` and `summary_fields()`.
- `server/api/mail.py:60` (`get_message`) fills them in.
- Update `tests/test_server_mail.py` using `tests/fake_imap.py`.
- Mirror the types in `frontend/src/model/mail-api.ts` (`Detail`).

## Frontend: shared Pinia mail store

- Add `pinia`, and `pinia-plugin-persistedstate` or a small hand-written localStorage plugin if that avoids a dependency.
  Persist only `accountId`, `folder`, `selectedUid`, and the pinned `detail`, never credentials. Wrap storage access in try/catch.
- Convert `model/mail-store.ts` (`createMailStore`) to a `defineStore`, keeping the same refs and actions so `mail-store.spec.ts` ports with small changes.
  `MailView.vue:10` stops creating it locally, `MailFolders`, `MailList` and `MailMessage` take it from `useMailStore()`.
- Register Pinia in `main.ts`. The rule store stays on provide/inject.

## Frontend: fill logic

New pure module `model/fill-from-mail.ts`, tested in a spec next to `catalog.spec.ts`:
- `mailDefaults(detail, accountId, folder)` returns the value for each field from the catalog (`model/catalog.ts` lists).
- `fillExpression(expr, detail, options)` returns an updated condition for the types text, address, header, number, date, bool and presence.
  - Skips `Var` fields (`isVar`, `model/types.ts:138`).
  - Address granularity maps to the existing `part`: name+email is `full`, email is `address`, name is `name`, plus `local_part` and `domain` by splitting. Multi-address fields (`to`, `cc`) take the first address, or use `in` with the list when the user picks "all".
  - Dates fill `date_received` and `date_sent` as an absolute time. Numbers fill `eq`, or keep the operator.
  - Header conditions look the header name up in `detail.headers`.
  - A field missing on the mail stays untouched.

## Frontend: UI

- Hoist the screen state: `AppShell.vue` shows a `MailPanel` beside the rules `.body` on desktop (toggle in the topbar, visible only when `online`).
  On mobile (same breakpoint the mail browser already uses) the panel is a subpage with a back button, the same `data-pane` pattern as `MailView.vue`.
  The panel reuses `MailFolders`, `MailList` and `MailMessage`.
- (b) Rule first: `ConditionNode.vue` node bar (lines 40-67) gets a "Fill from mail" button, disabled with a hint until a mail is open, and a granularity select for address conditions.
  It calls `fillExpression` and emits `update:modelValue`, so undo works as one step.
- (a) Mail first: `GroupEditor.vue` `add()` (line 8) calls `fillExpression(newExpression('text'), ...)` when a mail is open.
  `MailMessage.vue` header gets quick actions that add a condition for a field, such as "Rule from sender", with the same granularity choice. They append to the current rule's `when`, creating an `all` group if needed.
- Styling follows the existing SCSS, light and dark.

## Docs

- Update `ai/initial.md` stage 5 checklist and "Status so far", `CLAUDE.md` Layout (Pinia store, `fill-from-mail.ts`, extended `DetailOut`), and `README.md` if it documents the mail API.

## Commits (separate tasks, /commit-with-lplp-style)

1. Backend detail extension with tests.
2. Pinia store migration with persistence.
3. `fill-from-mail.ts` with Vitest.
4. Side panel, subpage on mobile, fill buttons, with Playwright.
5. Docs.

## Verification

- `uv run pytest` for the backend and `yarn test`, `yarn lint`, `yarn build` in `frontend/`.
- `yarn test:e2e`: extend `e2e/mail.spec.ts` mocks (`mockServer`, `DETAIL`) with the new fields, and add a spec that opens a rule, opens a mail in the panel, fills a `from` condition at each granularity, checks undo, the phone-width subpage, and that the pinned mail survives a reload.
  `/api/editor/rules` must return real YAML in that mock.
- No claude-in-chrome checks, Playwright only.
