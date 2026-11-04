# Improve the mail view

## Context

The mail browser is read-only and its message pane has no actions.
The user wants one scroll for header and body, a read/unread toggle, a "create or extend a rule" button, and a move button with a tree picker.
Reading and writing are separated on purpose: reads use `EXAMINE` and `BODY.PEEK`, and writes only happen when `ACTIONS_ENABLED=true`.
The new user-driven writes keep that rule, so the buttons are disabled with a hint while `mail.actionsEnabled` is false.

## 1. One scroll for header and body

- `frontend/src/components/MailMessage.vue` and `styles/main.scss` (~642-1015): `.mail-message` already scrolls as one column and the iframe has no inner scroll, so the remaining work is making that reliable.
- `fit()` only runs on `@load` and on uid change, so replace it with a `ResizeObserver` on the iframe's `documentElement` (images and fonts load late) and keep `min-height: 120px`.
- Check that the sticky `.pane-head` still works and that the single-pane phone mode and the compact side panel show no second scrollbar.
- Playwright check: the iframe's height equals its content height, and only `.mail-message` has a scrollbar.

## 2. Mark read / unread

- Backend: add `POST /api/mail/accounts/{id}/messages/{uid}/flags?folder=` in `server/api/mail.py` with body `{add: [], remove: []}`, using `imap_session` and `ImapClient.store_flags` (`ensure_writable` does the `SELECT`).
- Restrict to a small whitelist of system flags (`\Seen`, `\Flagged`, `\Answered`) so it is not a general flag writer.
- Gate on `settings.actions_enabled` and answer 409 `actions_disabled` like `api/dry_run.py`.
- The Watcher will log it as `user_action` (flags added or removed), which is the honest result, because `OwnChanges` only knows about rule actions.
- Frontend: `mail-api.ts` `setFlags(...)`, store action `mail.setSeen(uid, seen)` that updates `detail` and the row in `messages` (`seen`, unread dot), and a header button in `MailMessage.vue`.
- Opening a mail stays side-effect free: no auto mark-as-read.

## 3. Move

- Backend: `POST /api/mail/accounts/{id}/messages/{uid}/move?folder=` with body `{folder, account_id?}`, using `ImapClient.move` (same account only in this step, a cross-account target is refused with 422 because `ImapWriter.move_across` belongs to the action runner).
- Same gating and `409 actions_disabled`.
- Update the allow-list in `tests/test_server_mail.py::test_everything_is_read_only`: it still holds for the read routes, and the write routes get their own tests with `FakeServer`.
- Frontend: store action `mail.moveTo(uid, folder)` removes the row, picks the next message (or closes the pane) and reloads the folder counts.
- Header button `Move ▾` in `MailMessage.vue`:
  - The menu lists the distinct move destinations from the loaded rules (`file.rules[*].actions` of type `move`, filtered to the current account, `account_id` unset means the mail's account), most used first.
  - The last entry is `More …`, which opens a modal with the macOS-like tree.
- Tree component `MailFolderTree.vue`: real nesting from `folderLabel` and `delimiter`, disclosure triangles with expand/collapse, special-use icons, keyboard (arrows, left/right, enter), search filter, and synthetic parent rows for non-selectable parents (which `MailFolders.vue` drops today).
- Reuse the folder list already in `mail.folders`, and send the raw (modified UTF-7) `name` as the folder.
- The compact side panel (editor "Example mail") hides the write buttons, since it is for filling conditions.

## 4. Create a rule / add to an existing rule

- Header button `Rule ▾` in `MailMessage.vue`, which works only when rules are available (server file or database, or an open in-memory document), via the editor store.
- `New rule from this mail`: `store.addRule()`, then fill `locations` with the mail's account and folder and `when` with an `all` of conditions chosen with the existing helpers in `fill-from-mail.ts` (`conditionFor`, default `from` address and `subject` is not preselected), then navigate to `/rules/:index`.
- `Add to existing rule …`: pick a rule, then a target group in a small tree of its `when` (the root, each `all` / `any` / `not`), then the condition (reusing the field and granularity selects from `MailAddCondition.vue`).
- Generalize `appendCondition(when, added)` into `appendCondition(when, added, path = [])` that walks the path of group indexes and appends to an `all` / `any` (for `not` it wraps the child in an `all`), keeping the current top-level behaviour as the default so `MailAddCondition.vue` and its tests stay valid.
- Rules are edited client-side and saved as YAML, so no new server endpoint is needed.
  The editor store is on provide/inject, so the mail view needs access to it from outside the editor.
  Plan: lift the `useStore()` call into `AppShell` and pass it through the existing context, falling back to a disabled button when none is provided.
- The user saves from the editor afterwards, nothing is written silently.

## 5. Tests

- Python: new `tests/test_server_mail_write.py` for flags and move (success, whitelist, 409 when disabled, 502 on IMAP error, `FakeServer.commands` shows the `SELECT` and `UID STORE` / `UID MOVE`), plus the allow-list test.
- Vitest: `mail-store.spec.ts` for `setSeen` and `moveTo`, `fill-from-mail.spec.ts` for the nested `appendCondition`, a spec for the folder tree.
- Playwright: extend `e2e/mail-mock.ts` (the catch-all `**/api/mail/**` needs mocks for the new routes), and `e2e/mail.spec.ts` for the single scroll, the read toggle, the move menu and the tree, and the rule button.
- Per the project memory, the frontend is verified with Playwright only, and nothing touches the live account.

## 6. Docs

- Update `CLAUDE.md` with the durable facts from the exploration and the new decisions:
  - The mail browser is no longer read-only: flags and move endpoints exist, gated by `ACTIONS_ENABLED`, and user flag changes land in the log as `user_action`.
  - Layout facts: `.mail-message` is the single scroll column, the iframe is sized by a `ResizeObserver`, `appendCondition` takes a group path, the folder tree component, and the move menu fed by the rules' move destinations.
- Fix the Decisions bullet "Reading IMAP is read-only" and the mail browser bullet, which currently claim the browser never writes.

## Verification

- `uv run pytest`, `cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`.
- Run the dev server against a `FakeServer`-style setup only, never the live account.

## Open point

Writes are gated by `ACTIONS_ENABLED`, matching the documented rule that the server never writes to a mailbox otherwise.
If explicit user clicks should work regardless, the gate is one line in each new route.
