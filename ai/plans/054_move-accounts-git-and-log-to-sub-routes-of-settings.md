# Move accounts, git and log to sub-routes of settings

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

## Context

Todo `c522abcf` asks to move accounts under settings; the user added that git and log move there too.
Accounts, git and the action log are administration, so they become parts of Settings.
Result: `/settings` keeps today's content as the general part, `/settings/accounts`, `/settings/git` and `/settings/log` show the former screens, and the top bar loses the Accounts, Git and Log links.
The top bar keeps Rules, Mail, Settings and Log out.

## Findings

- `frontend/src/router.ts`: `Screen` has `'accounts' | 'git' | 'log'`, with routes `/accounts`, `/git`, `/log` and `/settings`.
- `AppShell.vue` (lines ~245-262, 277, 336-341): the three `RouterLink`s, the `screen !== 'mail' && screen !== 'log' && screen !== 'settings'` check that hides the editor buttons, and the `OnlineOnly` branches for log, accounts and git.
- `SettingsView.vue` is one `main.settings-view` with the sections Mail view, Offline cache, Rule editor, MCP server.
- `ActionLogView.vue` keeps its filters in the URL query via `router.replace({ query })`, which stays on the current route, so it works unchanged under `/settings/log`.
  The old `/log?...` links must keep their query when redirected.
- `ActionLogView` emits `unauthorized`, which `AppShell` handles with `logOut()`, so the log branch must stay rendered by `AppShell` (or `SettingsView` has to re-emit it).
- Tests that touch it: `components.spec.ts:183` (`/accounts`), `action-log.spec.ts` (mounts at `/log`, `/log?q=bill&kind=action`), `e2e/accounts.spec.ts` (clicks the `Accounts` link 8 times), `e2e/log.spec.ts` (`goto('/log')`, `toHaveURL(/\/log\?q=nothing/)`, `/\/log$/`), `e2e/git.spec.ts` (`goto('/git')`), `e2e/mcp-tokens.spec.ts` (`/settings`, unchanged).
- `CLAUDE.md` mentions `/log`, the accounts screen and the git screen in several places.

## Changes

1. `router.ts`:
   - Remove `'accounts' | 'git' | 'log'` from `Screen`.
   - Make `/settings` a parent with children `''` (name `settings`), `accounts` (`settings-accounts`), `git` (`settings-git`) and `log` (`settings-log`), all with `meta.screen: 'settings'`, using the nested-route pattern of the mail routes.
   - Redirects keeping old links and bookmarks working: `/accounts`, `/git` and `/log` to the new names, the `/log` one with `to.query` carried over (a function redirect).
2. `AppShell.vue`:
   - Drop the Accounts, Git and Log links and the three screen branches; `screen === 'settings'` renders `SettingsView`.
   - Keep `@unauthorized="logOut()"` on `SettingsView`, which re-emits it from the log part.
3. `SettingsView.vue`:
   - Add a sub-navigation at the top (`General`, `Accounts`, `Git`, `Log`; `RouterLink`s with the `current` class by route name, aria-label `Settings sections`).
   - Render by route name: `settings` shows the existing sections, the other three show `<OnlineOnly><AccountsView /></OnlineOnly>`, `GitView` and `ActionLogView` (with `@unauthorized` re-emitted).
   - Check the wrapper's width and padding while implementing, since the log table and the accounts form probably want the full width the old screens had (the general sections can keep a narrower inner wrapper).
4. Tests:
   - `components.spec.ts`: push `/settings/accounts` and assert the accounts section renders; assert `/accounts` redirects to `/settings/accounts`.
   - `action-log.spec.ts`: mount at `/settings/log...`; add one case that `/log?q=bill` redirects with the query kept.
   - `e2e/accounts.spec.ts`: replace the link clicks with `goto('/settings/accounts')`, and in one test click `Settings` then `Accounts` in the sub-nav to cover the navigation.
   - `e2e/log.spec.ts` and `e2e/git.spec.ts`: use the new paths and adjust the `toHaveURL` patterns.
5. `CLAUDE.md`: update the mentions (screens live under `/settings/...`, old paths redirect).

## Verification

- `cd frontend && yarn test`, `yarn lint`, `yarn build` (type check), `yarn test:e2e` (Playwright, no Chrome tools).
- Backend untouched.
