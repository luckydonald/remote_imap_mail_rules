Findings for `/Users/user/Documents/programming/Python/remote_imap_mail_rules/frontend`. All paths below are relative to that directory.

**App shell and routing**
- There is no vue-router. `package.json` lists only `vue`, `yaml`, `ajv` and `ajv-formats` as dependencies. `src/main.ts:5` is just `createApp(AppShell).mount('#app')`.
- `src/components/AppShell.vue` (198 lines) is the whole shell.
  - **Screen switch:** `const screen = ref<'rules' | 'accounts'>('rules')` is at line 20.
    - The topbar button at lines 113-120 toggles it. It only shows when `online` is true, i.e. when `/api/editor/config` answered.
    - Line 149 does the switch: `<AccountsView v-if="screen === 'accounts'" />`. Otherwise `<div class="body">` holds `RuleList` plus `<main>`.
    - `<main>` picks between `RuleEditor`, `TemplatesView` and `YamlPanel` using `store.view.value.kind`.
  - **Mail screen:** a mail browser fits as a third `screen` value (`'mail'`) with its own topbar toggle, a `v-else-if` branch next to line 149, and a new `MailView` component. Because the toggle is a single binary button, it would need to become a nav or a set of tabs.
  - **Other shell behaviour:**
    - `connect()` at lines 22-39 loads the server rules.
    - `notice` is the shared banner.
    - File drag-and-drop is handled at the `.app` root.
    - A global Ctrl/Cmd+Z handler is in `onKey`, lines 104-111.

**src/ layout**
- `src/components/` holds the views and rule editor:
  - `AppShell`, `AccountsView`, `RuleList`, `RuleEditor`, `TemplatesView`, `YamlPanel`
  - `ActionsEditor`, `LocationsEditor`, `ConditionNode`, `FieldValue`
- `src/components/condition/` holds one editor per condition type:
  - `TextLikeEditor` (text, address and header), `NumberEditor`, `DateEditor`, `BoolEditor`
  - `PresenceEditor`, `GroupEditor`, `TemplateUseEditor`, `TimeInput`
- `src/model/` holds the non-visual code:
  - `api.ts`, `accounts-api.ts`, `store.ts`, `context.ts`, `catalog.ts`, `types.ts`
  - `validate.ts`, `yaml-io.ts`, `comments.ts`, `values.ts`
- `src/styles/main.scss` is a single global stylesheet of 445 lines.
- `src/__tests__/` has one spec per model file plus `components.spec.ts`.
- The `@` alias points to `src`. `@schema` points to `../schemas/rules.schema.json` (`vite.config.ts:11-12`).
- The dev server proxies `/api` to `127.0.0.1:8000` (`vite.config.ts:17`).

**Components and SCSS conventions**
- Every component is `<script setup lang="ts">` with `defineModel` or `defineProps`/`defineEmits`.
- There are no scoped styles. All styling is global in `main.scss`, with flat class names (`.account`, `.account-form`, `.rule-list`, `.node`, `.leaf`, `.badge`, `.message`, `.hint`, `.ghost`).
- Nesting uses `&`.
- **Variables:** CSS custom properties on `:root` at `main.scss:1-15`. Names are `--bg`, `--panel`, `--text`, `--muted`, `--border`, `--accent`, `--accent-text`, `--danger`, `--ok` and `--node-*`.
- **Dark mode:** `@media (prefers-color-scheme: dark) { :root:not([data-theme='light']) {…} }` at lines 17-33. It only redefines the variables. There is no manual dark toggle, only the `data-theme='light'` override.
- **Responsive:** the only breakpoint is `@media (max-width: 760px)` at line 177. `.body` is `grid-template-columns: 260px minmax(0,1fr)` and collapses to `1fr`. A mail browser can reuse the same 760px breakpoint for a list/detail split.
- **Existing classes to reuse:**
  - `.app` (137) and `.topbar` (143)
  - `.body` (172), `.rule-list` (187) and `.badge` (239)
  - `.accounts` (409) and `.account` (415)
- **Rendering patterns to follow:** `AccountsView.vue` (163 lines) shows the usual pattern: `loading`, `message`, a `describe(error)` helper, and an inline form.

**API patterns**
- `src/model/api.ts` (65 lines):
  - `BASE = '/api/editor'`.
  - `fetchConfig` swallows errors and returns `null`, so the editor still works without a server.
  - `fetchRules` returns `null` on 404 and throws otherwise.
  - `saveRules` wraps failures in `SaveError` with a `messages: string[]`.
- `src/model/accounts-api.ts` (91 lines):
  - `BASE = '/api/accounts'`, plus `Account` and `AccountInput` interfaces.
  - `AccountError` carries `messages`.
  - The shared `failure(response)` helper at lines 38-54 handles FastAPI `detail` as either a string or a validation-error array, formatted as `loc.slice(1).join('.'): msg`.
  - The functions are `listAccounts`, `createAccount`, `updateAccount` and `deleteAccount`. They use plain `fetch`, check `response.ok`, throw `await failure(response)`, and cast the JSON.
  - A `mail-api.ts` should copy this shape: a `BASE` constant, an Error subclass with `messages`, and the `failure` helper.

**Store patterns**
- `src/model/store.ts`:
  - `createStore()` is a factory returning refs, computeds and functions, not Pinia.
  - It returns `view: ref<View>`, where `View` is `rule | templates | yaml` (line 8).
  - It also returns `file` (reactive), `undo`/`redo`, `load`, `problems`, `yaml`, `dirty`, `serverFile`, `markSaved`, `addRule`, `duplicateRule`, `removeRule`, `moveRule`, `usesOf` and `renameTemplate`.
- `src/model/context.ts`: the store is shared through `provide`/`inject` (`provideStore` and `useStore`, with the `STORE` key). `ALLOW_VARS` is a second injection key.
- The store covers the rules file only. Accounts state is local `ref`s inside `AccountsView`. Mail state could go in a separate `createMailStore` or in the view.

**Condition editing and where "fill from mail" attaches**
- `src/components/ConditionNode.vue` (82 lines) renders one node:
  - The type `<select>` is at lines 41-49.
  - The `.node-bar` toolbar (line 40) holds the wrap buttons `not(…)`, `all(…)`, `any(…)` and the remove button. It gets `node-bar` plus `spacer`, so a new button belongs in that bar before the wrap buttons.
  - It dispatches to the per-type editors at lines 66-81.
- `src/components/condition/TextLikeEditor.vue` (103 lines) handles `text`, `address` and `header`.
  - Each field is wrapped in `FieldValue`, which allows a `Var` in templates.
  - The value input is at lines 83-87, and the `in` operator uses a textarea.
  - A "fill from mail" button fits next to the value input, or in `ConditionNode`'s bar. It should be passed the selected mail and set `model.field`, `model.operator` and `model.value`.
- `GroupEditor.vue` handles `all`/`any`/`not` and calls `newExpression('text')` to add children.
- `NumberEditor`, `DateEditor`, `BoolEditor` and `PresenceEditor` are the other leaves. A mail-fill action would use `size`, `date_received`, `seen` and similar fields from the message.
- `RuleEditor.vue` (57 lines) hosts the top-level `when` node.
- `LocationsEditor.vue` holds `account_id` and `folder`, which a mail browser could also pre-fill.

**src/model/catalog.ts (112 lines)**
- It reads the field and operator enums straight from the JSON schema through `@schema` and an `enumOf(name)` helper over `$defs`.
- Exports: `textFields`, `addressFields`, `numberFields`, `dateFields`, `boolFields`, `addressParts`, `textOperators`, `compareOperators`, `presenceOperators`, `quantifiers`, `presenceFields`, `actionTypes` and `expressionTypes`.
- Also `typeLabels`, `operatorLabels` and `newExpression(type, templateNames)` at lines 77+.
- Defaults from `newExpression`:
  - `text`: field `subject`, operator `contains`.
  - `address`: field `from`, part `address`, operator `equals`.
  - `header`: name `X-Header`.
  - `date`: field `date_received`, a relative `7d` value.
- A "fill from mail" helper belongs here or in a new model file, mapping a mail message to an `Expression` built on `newExpression`.

**Tests**
- **Vitest:**
  - `vitest.config.ts` merges the vite config and uses the `jsdom` environment. It excludes `e2e/**`.
  - Specs are in `src/__tests__/*.spec.ts`.
  - API tests stub fetch with `vi.stubGlobal('fetch', vi.fn<typeof fetch>().mockResolvedValue(new Response(JSON.stringify(data), { status })))` and `afterEach(() => vi.unstubAllGlobals())` (`accounts-api.spec.ts:1-30`). They check URL, method and body from `mock.calls`.
  - Component tests in `components.spec.ts:1-30` use `@vue/test-utils` `mount`. The `withStore(child)` helper at lines 11-19 wraps a component in a host that calls `provideStore`.
  - `components.spec.ts` also mounts `AppShell`.
- **Playwright:**
  - `playwright.config.ts` runs Chromium only, `testDir ./e2e`, on port 5199 with `yarn vite --port 5199 --strictPort` as the web server. No real backend is needed.
  - The e2e specs are `editor.spec.ts`, `accounts.spec.ts` and `server.spec.ts`.
  - Mocking uses a `mockServer(page)` helper with `page.route('**/api/...')`. `accounts.spec.ts:21-48` shows the pattern: always mock `**/api/editor/config` (returns `mode: 'server'`) and `**/api/editor/rules` (404). Then mock `**/api/accounts**` with a switch on `request.method()`, recording non-GET requests into `mock.requests`, and `route.fulfill({ json | status | body })`.
  - A mail e2e spec should copy that helper and add `**/api/mail**` routes. It can use `page.setViewportSize` to test the responsive layout at 760px and below.