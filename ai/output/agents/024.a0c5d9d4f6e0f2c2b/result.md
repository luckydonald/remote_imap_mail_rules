## 1. Frontend mail view (`/Users/user/Documents/programming/Python/remote_imap_mail_rules/frontend/src`)

**Layout.** `components/MailView.vue` renders `<MailFolders/> <MailList/> <MailMessage :compact/>` inside `div.mail` with `data-pane=store.pane`.
- It syncs the store place with the URL (`/mail/:accountId/:folder/:uid`, via `locationOfMail` and `mailPlaceOfRoute` in `router.ts`). Both are skipped when `compact`.
- `compact` is the "Example mail" side panel. `AppShell.vue` mounts `<MailView compact>` in `aside.mail-panel` when `mail.panelOpen`. The toggle button there is labelled "Example mail".

**CSS** is in `styles/main.scss`, lines ~642-1015.
- `.mail` is a grid `220px 340px minmax(0,1fr)` with `height: calc(100vh - 52px)`.
- `.mail-folders, .mail-list, .mail-message` each have `overflow-y: auto; min-width: 0`.
- `.pane-head` is sticky at `top: 0`.
- `.body-frame` has `display:block; width: calc(100% - 32px); margin: 0 16px; min-height: 120px; border: 0; border-top: 1px solid var(--border); background:#fff`.
- The `@mixin single-pane` (one pane at a time) applies at `max-width: 760px` and in `.mail-view.compact`.
- So the header (subject, meta, attachments, add-condition) and the body iframe do NOT scroll separately today. The whole `.mail-message` column scrolls, and the iframe has no inner scroll.

**Iframe sizing** is in `MailMessage.vue`:
```ts
function fit() { const body = frame.value?.contentDocument?.documentElement
  if (frame.value && body) frame.value.style.height = `${body.scrollHeight}px` }
watch(() => props.store.detail?.uid, () => void nextTick(fit))
```
The iframe is `sandbox="allow-same-origin allow-popups allow-popups-to-escape-sandbox"`, `:srcdoc="frameDocument(store.detail.html)"` and `@load="fit"`. There is no resize observer.
- `frameDocument` (in `model/mail-format.ts`) adds a base style, `<base target="_blank">` and a `<body>`.
- With a plain-text mail it uses `<pre class="body-text">`. `MailLog :events` follows below the body.

**Header in `MailMessage.vue`**
- A `header.pane-head` with one button, `‹ Messages` (class `ghost back`, calls `store.back()`). It is only visible in single-pane mode.
- Then `<h2 class="subject">`, then `dl.meta` (From, To, Cc, Date via `addressList` / `fullDate`).
- Then `<MailAddCondition v-if="compact && store.context">`, then the `ul.attachments`.
- There are no action buttons (flag, mark read/unread, move, delete).

**Other components**
- `MailList.vue`:
  - Header with `‹ Folders` back button, folder name and total.
  - Each row is `button.row-mail` with classes `active` and `unread` (`!mail.seen`), plus a dot, from, date, subject and 🚩/📎 icons.
  - It calls `store.openMessage(uid)` and has a "Load older messages" button (`store.loadMore()`).
- `MailFolders.vue`: account `<select>` when more than one account, then a flat `ul` of `button.folder`. Indent is `paddingLeft: 12 + depth*16px`. It shows `folderIcon`, the label and an `unseen` count badge. Click calls `store.selectFolder(name)`.
- `MailAddCondition.vue`: field select (filtered by `conditionFor(...) !== null`), granularity select for address fields, and an "Add to the rule" button. It takes the rule at `store.view.value.index` of the editor store and does `rule.when = appendCondition(rule.when, condition)`. It is disabled unless the editor view is a rule.

**`model/mail-store.ts`** (Pinia `useMailStore`)
- State: `accounts`, `accountId`, `folders`, `folder`, `messages`, `total`, `nextBefore`, `detail`, `selectedUid`, `events`, `error`, `loading`, `foldersLoading`, `pane`, `panelOpen`, `active`, `actionsEnabled`.
- Computed: `context` (a `MailContext {detail, accountId, folder}`), `currentFolder`, `hasMore`.
- Actions: `loadAccounts(target?)`, `selectAccount`, `selectFolder(name, uid?)`, `loadMore`, `openMessage(uid)`, `goTo(place)`, `back`, `clear`, `setUnauthorizedHandler`.
- Race guards: `listTicket`, `detailTicket` and `eventsTicket`.
- Persistence: localStorage key `mail-browser`, saved as `{accountId, folder, uid, detail}`.
- `fail()` calls `onUnauthorized()` on a 401.
- Opening a message only does `getMessage` plus `loadEvents`. It never changes flags, and the server fetches with PEEK, so nothing is marked seen. `detail.flags`, `detail.seen` and `Summary.seen/flagged/answered` come from the server.
- Only folders with `selectable` are kept: `folders.value = found.filter(i => i.selectable)`.

**`model/mail-api.ts`** is read-only, with all calls under `/api/mail`:
- `listFolders(accountId)`: `GET /accounts/{id}/folders`
- `listMessages(accountId, folder, beforeUid, limit=50)`: `GET /accounts/{id}/messages?folder&limit&before_uid`
- `getMessage(accountId, folder, uid)`: `GET /accounts/{id}/messages/{uid}?folder`
- `listEvents(...)`: `GET /accounts/{id}/messages/{uid}/events?folder`
- Also `login` and `logout` under `/api/auth`.
- Types: `Folder`, `Summary`, `Detail {flags, keywords, headers, to/cc/..., text, html, attachments}`, `MailEvent {kind: 'first_seen'|'rule_match'|'action'|'user_action'}`.
- Shared helpers `json()` and `failure` come from `./http`.

## 2. Backend

**`server/api/mail.py`** is strictly read-only. Its docstring says so. The router is mounted at `/api/mail` behind login in `server/app.py` (`protected` dependency). `api/events.py` also mounts at `/api/mail`.

| Endpoint | Purpose |
|---|---|
| `GET /accounts/{id}/folders` | `list_folders` plus `folder_counts` (STATUS) per selectable folder |
| `GET /accounts/{id}/messages?folder&before_uid&limit` | `list_page`, newest first |
| `GET /accounts/{id}/messages/{uid}?folder` | `get_message`, with sanitized HTML and cid resolution |
| `GET /accounts/{id}/messages/{uid}/parts/{part}` | `get_part`, forced sandbox headers |
| `GET /accounts/{id}/messages/{uid}/events` | in `events.py` |

- There is no endpoint to change flags or move a mail.
- `server/imap_session.py`: `async with imap_session(request, session, account_id) as client` opens a fresh `ImapClient` per request. It maps errors to 404 (unknown account), 503 (`CryptoError`), 502 (IMAP errors, `OSError`) and 504 (`TimeoutError`).
- The read path uses `client.examine(folder)` (read-only) and `BODY.PEEK`. `tests/test_server_mail.py::test_everything_is_read_only` asserts that only `LOGIN/LOGOUT/LIST/STATUS/EXAMINE/UID FETCH/UID SEARCH` commands are sent. A write endpoint would have to extend that allow-list or be a separate test.

**`imap/client.py` `ImapClient`**
- `examine(folder)` is read-only and sets `writable=False`.
- `select(folder)` is read-write.
- `ensure_writable(folder)` calls `select` if `self.folder != folder` or the folder is not writable.
- `store_flags(folder, uid, add=(), remove=())` uses `UID STORE +FLAGS.SILENT` / `-FLAGS.SILENT`.
- `move(folder, uid, target) -> Moved(folder, uid?, uidvalidity?)` uses `UID MOVE`. Without MOVE it falls back to copy plus `delete`, and it refuses (`ImapError`) without UIDPLUS.
- Also `delete`, `append`, `fetch_raw`, `find_message_id`, `list_folders(pattern)`, `folder_counts`, `poll_state`, `fetch_message`, `list_page`.
- The module docstring says reading only uses EXAMINE and PEEK, and the write methods open the folder with SELECT.

**`actions.py`**
- The `Writer` protocol has `store_flags(mail, add, remove)` and `move(mail, folder, account_id=None) -> MovedTo`.
- `ImapWriter(client, targets, allow_move)` really writes. It supports cross-account moves via `move_across` (append to the target, then delete the source) and checks the `allow_move` guard (`move_loop`).
- `VirtualWriter` only does the bookkeeping for the dry run.
- `ActionRunner(settings, rule_file, factory, lookup, allow_move)` is an async context manager with `run(mail)` (re-fetches the mail, then `run_chain(..., ImapWriter(...))`).
- The `Step`, `Round`, `ChainResult`, `MovedTo` types and `plan_steps` / `execute_steps` / `flag_change` are also in `actions.py`.

**`api/dry_run.py`**
- `POST /api/dry-run` simulates the rules and never writes.
- `POST /api/dry-run/run` returns 409 `actions_disabled` unless `settings.actions_enabled`. Otherwise it uses `ActionRunner` and calls `watcher.write_actions(session, chain)`.
- `ACTIONS_ENABLED` is `server/settings.py::actions_enabled`. It reaches the frontend through `GET /api/editor/config` (`EditorConfig.actions_enabled`), which `AppShell` copies into `mail.actionsEnabled`.
- A new user write endpoint should probably follow the same pattern. It could be gated by that setting, or by a new one, and would use `ImapClient.store_flags` / `move` directly.

**`server/watcher.py`**
- `OwnChanges` (`acting`, `flags`, `moved`) keeps our own rule actions out of the user-action log.
  - `finished(key, before, result)` and `is_own(change)` decide whether a change is ours.
  - `Watcher.run_actions` wraps the runner call with `own.acting`.
  - `report(change, queue)` queues a `UserChange` unless the change is ours.
- `write_user_change` writes `EventKind.user_action` with `{"type":"flags","added":[...],"removed":[...]}` (system flags only; `IGNORED_FLAGS` are excluded) or `{"type":"gone"}`.
- A user flag change or move made through a new API would be logged as `user_action`, because `OwnChanges` only knows about rule actions. Since the Watcher is a separate connection and `OwnChanges` is created inside the watcher's per-account run, there is no shared hook for the API. Options are to log it as a user action anyway, which is the honest result, or to add a shared registry.
- The frontend already renders `user_action` via `describeUserAction` in `model/mail-format.ts` ("You marked it read", "It left the folder...").

**`server/mail_view.py`**: `FolderOut`, `SummaryOut`, `DetailOut` (`flags`, `keywords`, `headers`, ...), `folder_out`, `summary_fields`, `detail_fields`.

## 3. Editor: adding rules and conditions

**`model/store.ts`** (`createStore`, provided via `model/context.ts` `provideStore/useStore`)
- State: `file` (a reactive `RuleFile`), `view` (`{kind:'rule',index}|{kind:'templates'}|{kind:'yaml'}`), undo/redo through a JSON history.
- Rule operations: `addRule()` (pushes `newRule()` and selects it), `duplicateRule`, `removeRule`, `moveRule`.
- `newRule()` creates `{name:'New rule', enabled:true, locations:[{account_id:'',folder:'INBOX',recursive:false}], when:newExpression('text'), actions:[]}`.
- There is no store-level "add condition" method. Conditions are edited by mutating `rule.when` directly.

**`model/fill-from-mail.ts`**
- `conditionFor(field, ctx, granularity)` returns a filled leaf `Expression`, or `null` if the mail lacks that field.
- `fillExpression(expr, ctx, granularity)`, `textValues`, `numberValues`, `boolValues`, `addressPart`, `headerValues`.
- `appendCondition(when, added)` appends to the top-level `all` group, else wraps `[when, added]` in a new `all`. It handles only the top level, with no `any` / `not` / nested targets.
- `headerSuggestions(ctx, common)`.

**Components**
- `ConditionNode.vue` is recursive and handles type switching, `remove` and `fillExpression` per node via `mail.context`.
- `condition/GroupEditor.vue` handles `GroupAll | GroupAny | GroupNot`. Its `add()` pushes `fillExpression(newExpression('text'), mail.context)` into `model.conditions`. `not` has a single `condition`.
- Also `RuleEditor.vue` (shows `DryRunPanel v-if="mail.active"`), `RuleList.vue`, `ActionsEditor.vue`, `LocationsEditor.vue`, `FieldValue.vue`, and the editors under `condition/` (`TextLikeEditor`, `PresenceEditor`, `TemplateUseEditor` and others).
- `AppShell.vue` shows the editor, the "Example mail" toggle (`mail.panelOpen`) and the `.body.with-mail` grid.

**Router** (`router.ts`): `/rules` (yaml), `/rules/templates`, `/rules/:index` (name `rule`), `/accounts`, `/git`, `/mail/...`, `/log`. Helpers are `locationOfView` and `viewOfRoute`.

**Move destination in the model**
- Frontend (`model/types.ts` ~line 111): `{ type: 'move'; folder: Templatable<string>; account_id?: Templatable<string> }`. Locations are `{account_id, folder?, recursive}` (~line 105).
- Server (`rules/models.py` ~421): `MoveAction(type="move", folder: Templatable[str], account_id: Templatable[UUID] | None)`. If `account_id` is unset it means the mail's own account.
- The server's `api/editor.py` has only `GET /config`, `GET /rules` and `PUT /rules` (whole YAML text). `rules_store.py` has `RulesStore` (`exists`, `read_text`, `save_text`), `FileRulesStore`, `DatabaseRulesStore`, `rules_referencing(store, account_id)` and `replace_account_id`.
- So there is no server-side add-rule or add-condition API. All rule edits happen client-side on `file` and are saved as YAML. Creating a "move to folder X" rule from a mail means `store.addRule()`, then mutating `file.rules[i]` with `locations`, `when` and `actions: [{type:'move', folder, account_id}]`.

## 4. Folder tree

- `MailFolders.vue` is not a real tree. It is a flat list indented by depth.
- Depth comes from `folderLabel(folder)` in `model/mail-format.ts`: it splits `display_name` by `folder.delimiter`, and the name is the last segment.
- `folderIcon` maps `special_use` (inbox, sent, drafts, trash, junk, archive, flagged, all) to emoji.
- Server: `list_folders` returns `FolderOut{name (raw, modified-UTF7), display_name (decode_folder_name), delimiter, special_use, selectable, messages, unseen}`. The counts come from `folder_counts`, one STATUS call per folder (N calls).
- There is no collapse or expand and no parent placeholders. A non-selectable parent folder is dropped by the store filter (`selectable`), so a child can appear without its parent row.
- The raw `name` is what must be sent as `folder` (query param).

## 5. Tests

**Frontend unit tests** (`frontend/src/__tests__`)
- `mail-api.spec.ts` (84 lines) and `mail-store.spec.ts` (156 lines). The store spec has `describe('mail store')` (inbox opening and paging, restore after reload, 401, errors) and `describe('mail format')`.
- `fill-from-mail.spec.ts`, `store.spec.ts`, `components.spec.ts` (has a `MailLog` test), `dry-run.spec.ts`.

**Playwright e2e** (`frontend/e2e`)
- `mail-mock.ts` exports `ACCOUNT_ID`, `FOLDERS`, `summary(uid, seen)`, `DETAIL`, `EVENTS`, `mockServer(page, ...)` (routes `**/api/editor/config`, `**/api/editor/rules`, `**/api/auth/*`, `**/api/accounts`, `**/api/mail/**`) and `logIn(page)`.
- `mail.spec.ts` covers login, paging, reading, phone panes, spinners, URLs and deep links.
- `fill-from-mail.spec.ts` covers filling a condition from the side panel, adding a condition with a part, reload persistence, the phone subpage and header suggestions.
- Others: `editor`, `dry-run`, `log`, `accounts`, `git`, `server`.

**Python tests** (`/Users/user/Documents/programming/Python/remote_imap_mail_rules/tests`)
- `test_server_mail.py` (fixtures `server`, `client`, `account_id`): tests for login required, folders with counts, paging cursor, sanitized message and cid, detail headers and flags, parts served safely, not found, `test_everything_is_read_only` and `test_imap_failures` (502/504).
- `test_imap_write.py` covers `store_flags`, `examine` (read-only again), `move` (MOVE, copy+UID EXPUNGE fallback, refusal without UIDPLUS, new UID reporting) and `delete`.
- Also `test_actions.py`, `test_server_dry_run.py`, `test_server_watcher.py`, `test_server_events.py`, `test_imap_viewer.py`, `test_integration.py`.

**`tests/fake_imap.py`**
- `FakeServer(capabilities)` has `folders: dict[str, FakeFolder]`, `commands: list[str]` (the log of IMAP commands) and `push_queues`.
- Methods: `add(folder, uid, subject, flags="", sender=..., message_id=...)`, `set_flags(folder, uid, flags)`, `delete(folder, uid)` (simulates another client expunging), `push()`, `connect(settings)` (returns a `FakeConnection`).
- Supporting classes are `FakeMessage`, `FakeFolder`, `FakeProtocol`, `FakeConnection` and `fetch_lines`.
- In `test_server_mail.py` the app gets the fake through `app.state.imap_factory`.

## Planning notes
- A new mutating mail API needs: new routes in `server/api/mail.py` (flag set/unset, move) built on `imap_session` plus `ImapClient.store_flags` / `move`; a decision on `ACTIONS_ENABLED` gating; an update to the read-only test allow-list; and frontend `mail-api.ts` functions plus store actions that update `messages` and `detail`.
- Marking a mail read on open is currently not done.
- `appendCondition` needs a path or target parameter to support adding at nested `any` / `not` levels.
- The e2e `mockServer` has a catch-all `**/api/mail/**` route, so new endpoints need mocks there.