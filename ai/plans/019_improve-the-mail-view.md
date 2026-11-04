# Improve the mail view

## Context

The mail browser is read-only and its message pane has no actions, shows only sanitized HTML, and blocks remote images only by accident (the sanitizer drops `img src` for non-`cid:` values, and CORS-style blocking was never the intended mechanism).
The user wants one scroll for header and body, read/unread, rule creation from a mail, a move menu with a tree picker, a Text/HTML toggle with a setting, inline `cid:` images rendered, and a deliberate remote-image policy with its own settings and (later) rules.
Reads use `EXAMINE` and `BODY.PEEK`, and writes only happen when `ACTIONS_ENABLED=true`, so the new user-driven writes are gated the same way and their buttons are disabled with a hint while `mail.actionsEnabled` is false.

## 0. Use Pinia properly (prerequisite)

- The rule store (`createStore` in `model/store.ts`) is provided by `AppShell.vue` and read with `useStore()` from `model/context.ts` through provide/inject, so the mail view cannot reach it without lifting it.
- Convert it into a Pinia store with `defineStore` (`useRuleStore`, keeping the name `useStore` as the export if that keeps the diff small), so every component imports and calls it directly, and delete `provideStore` and the `STORE` key from `model/context.ts`.
- Touch points: `AppShell.vue` (stops creating and providing), `YamlPanel`, `RuleList`, `TemplatesView`, `RuleEditor`, `SourceMenu`, `ConditionNode`, `TemplateUseEditor`, `MailAddCondition`, `DryRunPanel`, and the specs `store.spec.ts` and `components.spec.ts` (use `setActivePinia(createPinia())` instead of building the store).
- Keep `ALLOW_VARS` as an injection key, because it is a per-subtree flag and not global state.
- Undo/redo history, `serverFile`, `dirty`, `documents` and the rest become Pinia state and actions unchanged, and the store must stay non-persisted (the mail store is the one cached in localStorage).
- Add a small `usePrefsStore` for the new view settings (section 8), persisted in localStorage with try/catch.

## 1. One scroll for header and body

- `frontend/src/components/MailMessage.vue` and `styles/main.scss` (~642-1015): `.mail-message` already scrolls as one column and the iframe has no inner scroll, so the work is making that reliable.
- `fit()` only runs on `@load` and on uid change, so replace it with a `ResizeObserver` on the iframe's `documentElement` and keep `min-height: 120px`.
- Check that the sticky `.pane-head`, the phone single-pane mode and the compact side panel show no second scrollbar.
- Playwright: the iframe height equals its content height, and only `.mail-message` scrolls.

## 2. Mark read / unread

- Backend: `POST /api/mail/accounts/{id}/messages/{uid}/flags?folder=` in `server/api/mail.py`, body `{add: [], remove: []}`, through `imap_session` and `ImapClient.store_flags` (`ensure_writable` does the `SELECT`).
- Whitelist `\Seen`, `\Flagged`, `\Answered`, gate on `settings.actions_enabled`, and answer 409 `actions_disabled` like `api/dry_run.py`.
- The Watcher logs it as a `user_action` (flags), which is accurate, because `OwnChanges` only knows about rule actions.
- Frontend: `mail-api.ts` `setFlags`, store action `setSeen(uid, seen)` updating `detail` and the list row, and a header button in `MailMessage.vue`.
- Opening a mail stays side-effect free.

## 3. Move

- Backend: `POST /api/mail/accounts/{id}/messages/{uid}/move?folder=`, body `{folder}`, through `ImapClient.move`, same account only (a cross-account move stays an action-runner feature), same gating.
- Frontend store action `moveTo(uid, folder)` removes the row, selects the next mail or closes the pane, and refreshes the folder counts.
- Header button `Move ▾`: the menu lists the distinct move destinations of the loaded rules (move actions for this account, an unset `account_id` meaning the mail's own, most used first), ending with `More …`, which opens a modal with the tree.
- New `MailFolderTree.vue`, macOS Finder-like: nesting from `folderLabel` and `delimiter`, disclosure triangles, special-use icons, arrow-key navigation, a filter field, and synthetic parent rows for non-selectable parents (`MailFolders.vue` drops them today).
- The raw (modified UTF-7) `name` is what is sent.
- The compact "Example mail" panel hides the write buttons.

## 4. Create a rule / add to an existing rule

- Header button `Rule ▾`, enabled when a rule document is available.
- `New rule from this mail`: `useStore().addRule()`, fill `locations` with the mail's account and folder and `when` with an `all` containing the `from` address condition (via `conditionFor`), then route to `/rules/:index`.
- `Add to existing rule …`: pick a rule, pick the target group in a small tree of its `when` (root, each `all` / `any` / `not`), then the condition using the field and granularity selects of `MailAddCondition.vue`.
- Generalize `appendCondition(when, added)` in `fill-from-mail.ts` to `appendCondition(when, added, path = [])`, appending to `all` / `any` at the path and wrapping the child of a `not` in an `all`, with today's top-level behaviour as the default.
- Everything is edited client-side and saved by the user from the editor, so no server endpoint is needed.

## 5. Text / HTML toggle

- New component `SegmentedToggle.vue`, a generic two-or-more button segment (`modelValue`, `options: {value, label}[]`, `role="radiogroup"`, current state highlighted), used as `[ Text | HTML ]` in the message header.
- `MailMessage.vue` shows `detail.text` in the existing `pre.body-text` path for Text and the sanitized iframe for HTML, falling back to the other one when a mail has only one part, with the toggle disabled for the missing one.
- Setting: `prefs.bodyMode` (`'html'` default, `'text'`), in `usePrefsStore`, changed by the toggle itself and by a settings section.
- Settings UI: add a small "Mail view" settings screen (`/settings`, linked from the nav) holding the body default and the remote-image policy, reusing `SegmentedToggle`.

## 6. Inline (`cid:`) embeds

- The sanitizer already rewrites `cid:` to the part URL, so first reproduce why it does not show reliably (inline types are limited to png, jpeg, gif and webp, and the part route, cookie and iframe `allow-same-origin` have to line up) with a fake mail that has a `multipart/related` image, then fix what is broken.
- Add `image/svg+xml` only if it is served with the forced `sandbox` CSP, otherwise leave it out.
- Tests: `test_server_mail.py` (rewritten URL, part served inline), and an e2e that the image has a non-zero `naturalWidth` in the iframe.

## 7. Remote images, blocked on purpose

- Clean in the sanitizer, not by browser accident: `sanitize_html(html, part_url, allow_remote=False)` in `server/html_sanitize.py` returns the cleaned HTML plus the list of blocked remote URLs (`img src`, and `srcset` / `background` if they get through, which they do not today), removing the `src` and recording the URL.
- With `allow_remote=True` (request query `remote_images=true`) it keeps `http` / `https` `src`, forces `referrerpolicy="no-referrer"` and `loading="lazy"`, and never allows `data:` or other schemes.
- `DetailOut` gains `blocked_images: list[str]` and `remote_images_allowed: bool`.
- Frontend: under the headers and before the body, when `blocked_images` is non-empty, an expandable `Blocked images (2)` block listing each URL as `<a href=url>url</a>` with the text equal to the href (`rel="noreferrer noopener"`, `target=_blank`), plus a `Load remote images` button that refetches the message with `remote_images=true`, for this mail only.
- Setting `prefs.remoteImages`: `'block'` (default), `'allow'` (always send the query), and `'rules'` (section 8).
- Tests: sanitizer unit tests for both modes, and an e2e for the list, the button and the setting.

## 8. Custom rule for auto-allowing remote images (last stage)

- A rule like the existing ones, built in the same rule builder: a new root key `remote_image_rules` in the rule file, a list of `{name, enabled, locations, when}` (same `when` expression, so sender, folder, list id and so on work), meaning "allow remote images for mails this matches".
- Model in `rules/models.py` (regenerate `schemas/rules.schema.json`), database rows follow the existing one-row-per-rule storage with a new table and migration, and the editor gets a section next to the rules and templates, reusing `RuleEditor` pieces without an actions editor.
- The mail detail endpoint evaluates them with `rules/evaluate.py` on the mail it already fetched, and answers `remote_images_allowed`, so the policy `'rules'` needs no extra client call.
- This stage is large and independent, so it is planned last and can land as its own change after sections 0 to 7.

## Tests

- Python: `tests/test_server_mail_write.py` (flags and move: success, whitelist, 409 disabled, 502, `FakeServer.commands` shows `SELECT` and `UID STORE` / `UID MOVE`), keep the read-only allow-list test for the read routes, sanitizer tests, and rule-file tests for stage 8.
- Vitest: Pinia conversion of `store.spec.ts` / `components.spec.ts`, `mail-store.spec.ts` (`setSeen`, `moveTo`), nested `appendCondition`, `SegmentedToggle`, the folder tree.
- Playwright (`e2e/mail-mock.ts` needs mocks for the new routes): single scroll, read toggle, move menu and tree, rule button, text/html toggle and default, inline image, blocked images list and load button.
- The frontend is verified with Playwright only, and nothing touches the live account.

## Docs

- Update `CLAUDE.md` with the durable facts and decisions:
  - The rule store is a Pinia store now (replace "The mail store is the only Pinia store, the rule store stays on provide/inject"), plus `usePrefsStore`.
  - The mail browser is no longer read-only: flag and move endpoints exist, gated by `ACTIONS_ENABLED`, and they show up as `user_action`.
  - `.mail-message` is the single scroll column, the iframe is sized by a `ResizeObserver`, `appendCondition` takes a group path, the folder tree, the move menu fed by rule destinations.
  - The sanitizer returns blocked remote URLs and the remote-image policy (`block` / `allow` / `rules`), and `remote_image_rules` in the rule file.
  - Fix the Decisions bullet "Reading IMAP is read-only" and the mail browser bullet.
- Save a feedback memory: use Pinia stores directly with `useStore()` in each file, no provide/inject for global state.

## Verification

`uv run pytest`, then in `frontend`: `yarn test`, `yarn lint`, `yarn build`, `yarn test:e2e`.

## Open point

Writes are gated by `ACTIONS_ENABLED`, matching the documented rule that the server never writes to a mailbox otherwise.
If explicit user clicks should work regardless, the gate is one line in each new route.
