# Plan: update banner shows again and again

## Context

Todo `1383606e`: "A new version of the app is available. [Reload] Later" comes multiple times and occasionally again without any new deployments.
The banner is `UpdateBanner.vue`, driven by `model/update.ts` (`registerType: 'prompt'`).
`AppShell` is the root component and mounted once, so the local `later` ref is not reset by remounts. That theory from the first check is ruled out.
The build could not be run here (no `node_modules` in this worktree), so I could not diff two builds; the `sw.js` side is unverified.

## Findings

- A waiting service worker stays waiting until every tab of the app is closed or `skipWaiting` is sent.
  Pressing "Later" and then reloading the page (or opening a second tab, or reopening the iPad/PWA window) does not activate it.
- On every such page load `registerSW` finds the same waiting worker again and calls `onNeedRefresh`, so the banner returns.
  That is the "again without any new deployment" case, and "multiple times" is one banner per load or tab.
- "Later" is only remembered in memory, so it never survives a load.
- Possible second cause, to check once dependencies are installed: `sw.js` may differ between builds of the same commit (Docker / Coolify rebuilds), which would be a real update without a deployment of new code.

## Change

1. `model/update.ts`: when the page loads and a waiting worker already exists, apply it at once instead of asking.
   A fresh load has no unsaved rule edits, so reloading it is safe, and the banner only appears for a worker that finishes installing while the page is open.
   Implement through the `onRegisteredSW` registration: if `registration.waiting` is set at registration time, call `applyUpdate()` (guard against loops with a `sessionStorage` flag set before the reload, cleared after a successful start).
2. Keep `Later` per page, but also remember the dismissal for this session in `sessionStorage`, keyed by the new worker, so a second tab or in-session navigation does not re-ask.
3. If the build diff shows `sw.js` is not deterministic, fix the cause (for example the precache revision of `index.html`), and note it in `CLAUDE.md`.

## Tests

- `src/__tests__/update.spec.ts`: a registration with `waiting` set at start applies the update and shows no banner; a worker that arrives later still shows the banner; the loop guard stops a second automatic apply in one session; dismissal persists in `sessionStorage`.
- Run `yarn install`, then `yarn test`, `yarn lint`, `yarn build`, and `uv run pytest`.
- Build twice and `diff -r` the two `dist` folders to settle point 3.

## Docs

Update the offline paragraph in `CLAUDE.md`: a waiting worker found at page load is applied automatically, the banner is only for one that arrives while the page is open.
