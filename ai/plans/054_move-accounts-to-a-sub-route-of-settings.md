# Move accounts to a sub-route of settings

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

## Context

Todo `c522abcf`: the Accounts screen at `/accounts` has its own top-bar link, but accounts are configuration and belong under Settings.
Result: `/settings` keeps today's content as the general part, `/settings/accounts` shows the accounts screen, and the top bar loses the Accounts link.

## Findings

- `frontend/src/router.ts`: `Screen` has `'accounts'`, route `/accounts` (name `accounts`), `/settings` (name `settings`).
- `AppShell.vue` (lines ~245, 277, 339-340): the Accounts `RouterLink`, the `screen !== 'settings'` check that hides the editor buttons, and the `AccountsView` branch wrapped in `OnlineOnly`.
- `SettingsView.vue` is one `main.settings-view` with the sections Mail view, Offline cache, Rule editor, MCP server.
- `AccountsView.vue` is a self-contained `section.accounts`.
- Tests that touch it: `src/__tests__/components.spec.ts:183` (`router.push('/accounts')`), `e2e/accounts.spec.ts` (clicks the `Accounts` link 8 times after `goto('/')`), `e2e/mcp-tokens.spec.ts` (`goto('/settings')`).
- `CLAUDE.md` mentions the accounts screen in the frontend paragraph.

## Changes

1. `router.ts`:
   - Remove `'accounts'` from `Screen`.
   - Make `/settings` a parent route with children: `''` (name `settings`) and `accounts` (name `settings-accounts`), both `meta.screen: 'settings'`, via the same nested-route pattern as the mail routes.
   - Add `{ path: '/accounts', redirect: { name: 'settings-accounts' } }` so old links and bookmarks keep working.
2. `AppShell.vue`: drop the Accounts link and the `accounts` branch, and let the `settings` screen render `SettingsView` (which now decides between the two parts).
3. `SettingsView.vue`: add a small sub-navigation at the top (`General` / `Accounts`, `RouterLink`s with the `current` class by route name, aria-label `Settings sections`).
   - On `settings-accounts` render `<OnlineOnly><AccountsView /></OnlineOnly>` instead of the general sections.
   - The accounts form keeps its own layout, so the existing `main.settings-view` wrapper only changes to a plain wrapper for the shared sub-nav if the CSS needs it (check the width and padding while implementing).
4. Tests:
   - `components.spec.ts`: push `/settings/accounts` and assert the accounts section renders, plus a case that `/accounts` redirects to `/settings/accounts`.
   - `e2e/accounts.spec.ts`: replace `getByRole('link', { name: 'Accounts' }).click()` with `goto('/settings/accounts')` (or a small helper that clicks `Settings` then `Accounts` in the sub-nav in one test so the navigation path is covered).
   - Keep `mcp-tokens.spec.ts` as is.
5. `CLAUDE.md`: update the frontend paragraph (accounts screen is `/settings/accounts`, `/accounts` redirects).

## Verification

- `cd frontend && yarn test`, `yarn lint`, `yarn build` (type check), `yarn test:e2e` (Playwright, as the repo requires; no Chrome tools).
- Backend untouched, so no `uv run pytest` needed beyond a smoke run if time allows.
