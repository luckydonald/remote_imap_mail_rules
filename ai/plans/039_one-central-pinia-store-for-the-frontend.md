# One central Pinia store for the frontend

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

## Context

The rule "use Pinia stores directly, `useX()` per file, no provide/inject" was misread as "make a separate store per concern".
The frontend now has five stores: `useStore` (rules, `model/store.ts`), `useMailStore` (`mail-store.ts`), `usePrefsStore` (`prefs.ts`), `useClipboardStore` (`clipboard.ts`) and `useMenuStore` (`menu.ts`).
They reach into each other (`mail-store` and `clipboard` read prefs, `AppShell` writes `mail.actionsEnabled` from the editor config), and account data is fetched twice: `ActionLogView.vue` calls `listAccounts()` itself while `useMailStore().accounts` already holds the list.
The intent is one central store for everything about mails and rules, and local state only where it is really local.

## Target shape

- One `defineStore('app', …)` exported as `useStore` from `src/model/store/index.ts` (the renamed `mail-store.ts`), so the 20-odd files that already call `useStore()` keep working, and `useMailStore` / `usePrefsStore` / `useClipboardStore` / `useMenuStore` go away.
- A setup store of 1500+ lines is unreadable, so each merged store moves into a plain function in its own file (`model/store/rules.ts`, `prefs.ts`, `clipboard.ts`, `menu.ts`, and `mail.ts` if `index.ts` grows too big) that returns refs and functions, and the one `defineStore` calls them and spreads the results.
  These are not stores: no `defineStore`, no `useX()` of their own, shared state is passed in as arguments (e.g. the mail part takes `prefs`).
- Names stay as they are (`store.accounts`, `store.bodyMode`, `store.cut()`), so components change only their import and the variable (`mail.` / `prefs.` / `clipboard.` becomes `store.`).
  A name clash (`folder`, `view`, `load`, `clear`) is renamed at the clash, not prefixed everywhere.
- Kept out on purpose: `ALLOW_VARS` (per-subtree injection flag), component-local `ref`s (form fields, `loading`, `message`, `confirming`, dry-run page state), the localStorage keys `mail-browser` and `mail-prefs` (same keys and shapes, so nothing saved is lost; they are now written by the central store).
- Menus: `useMenu(id, root)` stays an exported composable (it needs `onMounted`), but its shared slot (`openId`) moves into the central store.
- `ActionLogView.vue` drops its own `listAccounts()` and uses `store.accounts` (calls `loadAccounts()` / `refreshAccounts()` when empty, as `MailView` does).
- `AccountsView.vue` already shares the list (previous commit); check it keeps only local form state.

## Base of the central store: `mail-store.ts`

The user wants the existing `mail-store.ts` (it already holds accounts, folders, messages, the open mail, `context`, `actionsEnabled`, the storage) as the base, so it is renamed first and the other stores are merged into it.
`model/store.ts` (the rules store, currently `useStore`) is in the way of that name, so the rename is two pure moves in one commit, content identical, only import paths change (26 files import them, `git mv` keeps the history):

- `model/mail-store.ts` becomes `model/store/index.ts` (the central store; `import … from '@/model/store'` resolves to it).
- `model/store.ts` becomes `model/store/rules.ts` (the rules part, to be turned into a composable in the next commit).
- The specs follow (`mail-store.spec.ts`, `store.spec.ts` keep their names for now, only imports change).

The composable files then live next to it: `model/store/rules.ts`, `prefs.ts`, `clipboard.ts`, `menu.ts`, and the mail part stays in `index.ts` or moves out to `mail.ts` once the file is too big to read (decide when merging; `index.ts` is only the `defineStore` that calls them).

## Commits (one per store / local data file)

Each commit keeps `yarn test`, `yarn lint` and `yarn build` green, and moves code before changing it (rule 8): the move into the central store is one commit with the code unchanged, call sites follow in the same commit.

0. Pure renames (above): `mail-store.ts` to `store/index.ts` and `store.ts` to `store/rules.ts`, imports fixed, still two stores.
1. Rules store into the central one: `useMailStore` becomes `useStore` (id `'app'`), `store/rules.ts` turns into a plain `useRulesState()`-style function (no `defineStore`) whose return is spread into the central store, and the old `useStore` call sites keep working because the name now points to the central store.
   Every `useMailStore()` call site becomes `useStore()`; where one component used both (`RuleEditor`, `AppShell`, `ConditionNode`, …) it ends with a single `store`.
2. `prefs.ts` into the central store.
   Move `bodyMode`, `remoteImages`, `mailStyles`, `copyCut`, `readPaste` and the localStorage watcher.
   Update `SettingsView.vue`, `MailMessage.vue`, `mail-store.ts`, `clipboard.ts`, the tests.
3. `clipboard.ts` into the central store.
   `block`, `canPaste`, `cut`, `read`, with `parseExpressionText` staying an exported helper; update `ConditionNode.vue`, `GroupEditor.vue`, `clipboard.spec.ts`.
4. `menu.ts` into the central store (`openId` and its functions; `useMenu` stays); update `MailMoveMenu.vue`, `MailRuleMenu.vue`, `menu.spec.ts`.
5. Split the mail part out of `store/index.ts` into `store/mail.ts` (a composable taking `prefs`), so `index.ts` is only the `defineStore` that composes `rules`, `mail`, `prefs`, `clipboard` and `menu`; the `mail-browser` storage, `actionsEnabled`, `context`, `fillDetached` / `fillContext` and the unauthorized handler move with it unchanged.
   Pure move, no behaviour change; skip this commit if `index.ts` is still readable after the merges.
   The component props that pass `store` / `mail` down (`MailMoveMenu`'s `props.store`) use the central store directly in this step or the call-site updates above.
6. Remove the duplicate account fetch in `ActionLogView.vue`, using `store.accounts`; add or adjust a test (the log screen does not call `/api/accounts` itself).
7. Audit pass: grep for any remaining `defineStore`, `listAccounts`, `localStorage` and direct `*-api` fetches of data the store already owns (`fetchConfig` result is split between `AppShell` and the store: keep it in one place, `actions_enabled` included).
   Only commit if something is found.
8. Docs and memory, last commit.
   - `CLAUDE.md`: rewrite the Pinia sentences in the `frontend/` and "Fill from mail" bullets (they list four store names) to say there is one central store `useStore`, split into plain composable files, and that new global state goes into it unless it is a totally different concern.
   - Memory `feedback_pinia_not_inject.md` (both `~/.claude/projects/…/memory/` and the repo's `ai/memory/` copy) and its line in `MEMORY.md`: rename to a "one central store" feedback, with **Why:** the per-store reading was a misunderstanding and duplicates (like the account list) crept in, and **How to apply:** one `defineStore`, per-file `useStore()`, no provide/inject, split files by composable functions not by store, add a second store only for a really unrelated concern and ask first.
   - The `ai/` plans that mention the old store names are history, not touched.

Commit messages: `[frontend] stores: ai: Run: Moved … into the central store.` (reuse the label from `git log --oneline -5 -- <file>`), message via `ai/git/pending-commit.md`, then `./scripts/tag_backup.py`, then fold the `ai:` auto-commits; no trailers (rule 10, overrides the session attribution reminder).

## Verification

- `cd frontend && yarn test` (Vitest: the store, clipboard, menu and mail-store specs are rewritten to `useStore()`), `yarn lint`, `yarn build` (type check) after every commit.
- `yarn test:e2e` (Playwright, also `webkit-ipad` for `mail.spec.ts`) after commits 4 and 5; Playwright mocks `/api`, so nothing touches a real mailbox.
- `grep -rn "defineStore" frontend/src` shows exactly one hit at the end, and `grep -rn "listAccounts" frontend/src` only in the store and `accounts-api.ts`.
- Reload test by hand or e2e: the saved place (`mail-browser`) and the prefs (`mail-prefs`) still restore.

## Decisions taken (change if you disagree)

- Prefs and menu go in too, not only mail and rules: prefs mix mail view and rule-editor clipboard settings, so they cut across both, and the menu slot is tiny.
- Split by composable files inside one store, not by store.
