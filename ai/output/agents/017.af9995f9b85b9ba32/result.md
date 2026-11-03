Frontend root: `/Users/user/Documents/programming/Python/remote_imap_mail_rules/frontend/src`. Backend: `/Users/user/Documents/programming/Python/remote_imap_mail_rules/src/remote_imap_mail_rules/server`. Paths below are relative to those two roots unless they start with `/`.

## 1. Editor UI structure

**Components**
- `components/AppShell.vue` creates and provides the rule store (`createStore()` at line 15, `provideStore(store)` at line 16). It also owns screen switching.
- `components/RuleEditor.vue` (57 lines) has one `<ConditionNode v-model="model.when" />` under the "When" heading (line 53). Its props are `rule` (a `defineModel`) and `index`.
- `components/ConditionNode.vue` (82 lines) is the recursive node.
  - Props: `modelValue: Expression` and `removable?`. Emits `update:modelValue` and `remove`.
  - Its `node-bar` (lines 40-67) holds the type `<select>`, the wrap buttons not(…)/all(…)/any(…) and the ✕ remove button.
  - `changeType(type)` (line 21) emits `newExpression(type, templateNames)`, so changing the type resets the condition to its defaults.
  - It dispatches to the leaf editors in lines 68-80. This node bar is the natural home for a "fill from mail" button.
- `components/condition/GroupEditor.vue` handles adding: `add()` (line 8) pushes `newExpression('text')` into `conditions`. Its "+ Add condition" button (line 32) is the mail-first hook point. A new rule in `store.ts` also gets a default condition (see `newRule()`).
- Leaf editors in `components/condition/`:
  - `TextLikeEditor.vue` covers text, address and header. It uses `defineModel<TextCondition | HeaderCondition | AddressCondition>('node')` and mutates `model.value` in place. `setOperator` converts a string value to an array when the operator is `in`.
  - `NumberEditor.vue`, `DateEditor.vue`, `BoolEditor.vue`, `PresenceEditor.vue`, `TemplateUseEditor.vue` and `TimeInput.vue` handle the rest.
- `components/FieldValue.vue` wraps each field so it can be a literal or a `Var` (`{var}`). Vars are only allowed inside templates (`ALLOW_VARS` in `model/context.ts`). Fill must skip `Var` fields, or at least not overwrite them. `isVar` is at `model/types.ts:138`.

**Types**: `model/types.ts` has one interface per condition, and `Expression` is the union (line 91).
- `TextCondition`: `{type:'text', field, operator, value: string|string[], case_sensitive?, quantifier?}` (line 26).
- `AddressCondition`: `{type:'address', field, part?, operator, value, case_sensitive?, quantifier?}` (line 44).
- `HeaderCondition`: `{type:'header', name, operator, value, ...}` (line 35).
- `NumberCondition`: `{field, operator, value: number|[n,n]}` (line 54).
- `DateCondition`: `{field, operator, value: TimeValue|[TimeValue,TimeValue]}` (line 62). `TimeValue` is `{relative:boolean, value:string}`.
- `BoolCondition`: `{field, value?: boolean, quantifier?}` (line 69).
- `PresenceCondition`: `{field?, header?, operator?, value?}` (line 76).

**Catalog** (`model/catalog.ts`)
- The field lists are read from the generated JSON schema (`@schema`): `textFields`, `addressFields`, `numberFields`, `dateFields`, `boolFields`, `addressParts`, `textOperators`, `compareOperators`, `presenceOperators`, `quantifiers` (lines 15-24).
- The enums live in `src/remote_imap_mail_rules/rules/fields.py`.
  - Text: account_id, folder, subject, body_text, body_html, message_id, in_reply_to, references, list_id, auto_submitted, precedence, importance, mime_type, keywords, auth_*, attachment_mime_type, attachment_filename, attachment_extension.
  - Address: from, sender, reply_to, return_path, to, cc, bcc, recipients, delivered_to.
  - Address part: full, name, address, local_part, domain.
  - Number: size, spam_score, attachments_count, attachment_size, uid, modseq.
  - Date: date_sent, date_received.
  - Bool: seen, flagged, answered, draft, deleted, spam_flag, is_reply, has_list_unsubscribe, attachment_inline.
- `newExpression(type, templateNames)` (line 83) creates the defaults:
  - text: `{field:'subject', operator:'contains', value:''}`
  - address: `{field:'from', part:'address', operator:'equals', value:''}`
  - header: `{name:'X-Header', operator:'contains', value:''}`
  - number: `{field:'size', operator:'gt', value:0}`
  - date: `{field:'date_received', operator:'lt', value:{relative:true, value:'7d'}}`
  - bool: `{field:'seen', value:true}`
  - presence: `{field:'subject', operator:'exists', value:true}`
  - groups wrap a single text condition.
- Also in `catalog.ts`: `typeLabels`, `operatorLabels` and `expressionTypes`.

**Store** (`model/store.ts`)
- `createStore(initial)` (line 26) returns: `file` (reactive `RuleFile`), `view`, `fileName`, `serverFile`, `dirty`, `markSaved`, `canUndo`, `canRedo`, `problems`, `yaml`, `undo`, `redo`, `load`, `addRule`, `duplicateRule`, `removeRule`, `moveRule`, `usesOf`, `renameTemplate`.
- There are no per-condition operations. Components mutate `file` directly through `defineModel`, or by emitting `update:modelValue`.
- Undo is a JSON-snapshot watcher on `file` (lines 48-59), so any in-place mutation is automatically one undo step.
- `View` is `{kind:'rule', index} | {kind:'templates'} | {kind:'yaml'}` (line 8).
- A fill helper therefore belongs in a pure `model/` module that takes a `Detail` and a `Expression` (or a type plus granularity) and returns an `Expression`. Cases that fit this are `fillFromMail(expr, detail, granularity)` and `mailDefaults(detail)`.

## 2. Mail browser state and screen switching

**`model/mail-store.ts`** (166 lines)
- `createMailStore(onUnauthorized)` returns refs: `accounts`, `accountId`, `folders`, `folder`, `currentFolder`, `messages` (`Summary[]`), `total`, `hasMore`, `detail` (`Ref<Detail|null>`), `selectedUid`, `error`, `loading`, `foldersLoading`, `pane`. It also returns the actions `loadAccounts`, `selectAccount`, `selectFolder`, `loadMore`, `openMessage(uid)` (line 119) and `back`.
- The currently open message is `store.detail.value` (null while loading or when none is selected). `store.accountId.value` and `store.folder.value` give its location, which is useful for the `account_id` and `folder` text fields.
- It is not shared. `MailView.vue` line 10 calls `createMailStore(...)` locally, and `MailView` is unmounted when the screen changes. The mail state is lost on switching to Rules, and the editor cannot see it.
- To implement this, hoist the mail store into `AppShell`, either with `provide/inject` like the rule store in `model/context.ts` or as a prop to `MailView`. Add an injection key and a `useMailStore()` next to `provideStore`/`useStore`.

**`model/mail-api.ts`**: `Address {name, address}`, `Summary`, `Attachment`, `Detail`, `getMessage(accountId, folder, uid)` (line 94). The fields are in section 3.

**Components**
- `components/MailView.vue` (33 lines) lays out the three panes with `data-pane`. It contains `MailFolders`, `MailList` and `MailMessage`, and each takes the `store` prop.
- `components/MailMessage.vue` (71 lines) renders the `detail`: subject, From/To/Cc/Date, non-inline attachments, and the body (iframe for html, `<pre>` for text). A "Use for rule" action could go in its header area (lines 25-27) or `.meta`.
- `components/MailList.vue`: lists the messages, with Summary data only.
- `model/mail-format.ts` (71 lines): `addressList`, `fileSize`, `fullDate`, `personLabel` (line 28, name or address), `folderLabel`, `shortDate`, `frameDocument`.

**`AppShell.vue` screen switching**
- `screen = ref<'rules'|'accounts'|'mail'>('rules')` (line 24). The nav buttons (shown only when `online`) set it (lines 71-83).
- The template (lines 129-146) is a `v-if` / `v-else-if` chain: `MailLogin`, then `MailView` for `mail`, then `AccountsView` for `accounts`, else the rules `.body` with `RuleList` and `RuleEditor`/`TemplatesView`/`YamlPanel`.
- The two screens are mutually exclusive (`v-else-if`), so the editor and the mail screens cannot both be visible. This is also why `MailView` is destroyed when you leave it.
- The topbar editor buttons are hidden on the mail screen (`v-if="screen !== 'mail'"`, line 98).
- The editor is only reachable with `online` for the mail screen. A standalone file-based editor has no mail, so "fill from mail" must be hidden or disabled when offline or when no mail is open.
- Design implication for "mail first": with exclusive screens, either add a "Create rule/condition from this mail" action on the mail screen that switches `screen` to `rules`, or show a side panel. For "rule first": a mail picker is needed, or a button that jumps to the mail screen and returns with a selection.

## 3. Message detail type (backend)

`server/mail_view.py`
- `AddressOut {name, address}` (line 24).
- `SummaryOut` (line 29): `uid:int, sender:AddressOut, subject:str, date:datetime|None, seen, flagged, answered, has_attachments (non-inline only), size:int|None`.
- `AttachmentOut` (line 41): `part, filename, mime_type, size, inline, content_id, url`.
- `DetailOut(SummaryOut)` (line 51): `to[], cc[], reply_to[], message_id, text, html (sanitized), attachments[]`.
- `summary_fields(mail)` (line 86) parses `From` with `parseaddr`. `addresses(mail, header)` (line 80) uses `getaddresses`.
- The endpoint is `GET /api/mail/accounts/{id}/messages/{uid}?folder=` in `server/api/mail.py:60`, `get_message`. It builds `DetailOut` at lines 73-82.
- The frontend `Detail` in `model/mail-api.ts:45` mirrors this one to one.

Gaps for filling conditions. The domain `Mail` (`src/remote_imap_mail_rules/mail.py:42`) has more than `DetailOut` exposes:
- `Mail` has `headers` (an email `Message`), `flags`, `date_received`, `size`, `modseq`, `mime_type` and `attachments`.
- `DetailOut` lacks: arbitrary headers (needed for header conditions and for list_id, in_reply_to, references, auto_submitted, precedence, importance, auth_*), bcc, sender/return_path/delivered_to, `date_sent` (`date` is probably `date_received`), `draft`/`deleted`/keywords, `mime_type`, `modseq`, and `account_id`/`folder` (the frontend can get these from the mail store).
- `Attachment.extension` exists in the domain class but is not in `AttachmentOut`. The frontend can derive it from `filename`.
- Fillable today with no backend change:
  - text: subject, message_id, attachment_filename, attachment_mime_type, attachment_extension (derived), folder, account_id
  - address: from, to, cc, reply_to
  - number: size, attachments_count (computed), attachment_size (sum or max, ambiguous), uid
  - date: date_received
  - bool: seen, flagged, answered
- Header, other-address and other-bool fields need `DetailOut` extended, for example with a `headers: list[tuple[str,str]]` or a dict, plus `flags`/`keywords`.
- If the backend is extended, `schemas` are probably not affected, because this is the mail API, not the rules schema. `tests/test_server_mail.py` and the `Detail` mocks in the frontend tests would need the new fields.

Granularity mapping to existing concepts. `AddressCondition.part` is `full|name|address|local_part|domain`:
- "name+email" maps to `part: 'full'`, value `Name <addr>` (check how evaluate formats `full`)
- "email" maps to `address`
- "name" maps to `name`
- `local_part` and `domain` come for free by splitting the address.
- For multi-address fields (to, cc), use the `in` operator with a list, or `quantifier: any`.

## 4. Existing test patterns

**Vitest** (`vitest.config.ts`, `yarn test` runs `vitest run`; specs in `src/__tests__/`)
- `store.spec.ts`: pure store tests (`createStore()`, undo/redo, `renameTemplate`, server dirty state). A fill helper would get a pure-function spec like `catalog.spec.ts`.
- `catalog.spec.ts`: tests `newExpression`, the field lists and the schema.
- `components.spec.ts`:
  - `withStore(child)` (line 12) mounts a host that calls `provideStore(store)` and renders the child with `h()` via `@vue/test-utils` `mount`.
  - `ConditionNode` tests (line 23): nested groups, `button.add` click, `update:modelValue` emitted on type change.
  - `AppShell` test (line 70).
  - New tests for the fill button would copy `withStore` and also provide the mail store.
- `mail-store.spec.ts`:
  - `stubServer()` (line 28) is a `vi.fn<typeof fetch>` router by URL (`/api/accounts`, `/folders`, `before_uid=`, `/messages?`, else detail).
  - Fixtures are `mail(uid): Summary` (line 15) and `folder(...)`. The detail stub spreads `mail(3)` and adds `to`, `cc`, `reply_to`, ... (line 43).
  - Tests call `createMailStore()`, `await store.loadAccounts()`, `await store.openMessage(3)`.
- Also: `mail-api.spec.ts`, `accounts-api.spec.ts`, `api.spec.ts`, `yaml-io.spec.ts`.

**Playwright e2e** (`e2e/*.spec.ts`, `yarn test:e2e`)
- `mail.spec.ts`:
  - fixtures `FOLDERS`, `summary(uid, seen)` (line ~22) and `DETAIL` (line ~34, with a `report.pdf` attachment).
  - `mockServer(page, wrongPassword)` (line ~59) mocks `**/api/editor/config` (401 until login), `/api/editor/rules`, `/api/auth/login`, `/api/auth/logout`, `/api/accounts` and `**/api/mail/**` through `page.route`.
  - `logIn(page)` helper.
  - The main flow test (line 124) logs in, clicks the Mail nav button, clicks `.row-mail`, and asserts on `.mail-message h2`, `.meta` and `.attachments`.
  - Others cover responsive panes (line 169) and spinners (lines 186-228).
- `editor.spec.ts`: file-based, `openFile(page, name)` via `input[type=file]`, asserts on `.notice`, `.topbar .badge.ok` and `.rule-list`.
- `accounts.spec.ts` and `server.spec.ts` follow the same route-mocking style.
- An e2e for this feature would reuse `mockServer`, open a rule on the Rules screen, switch to Mail, and so on. The mock server also needs `/api/editor/rules` to return real YAML, because it currently returns 404.

**Backend tests**: `tests/test_server_mail.py` (the mail endpoints), `tests/test_imap_viewer.py` and `tests/fake_imap.py`. These matter if `DetailOut` is extended.

Open design points for the plan:
1. Hoist the mail store above the screen switch, because it is currently local to `MailView`.
2. Decide on one screen at a time versus a split or side-panel layout.
3. Decide whether to extend `DetailOut` with headers and flags.