# Fix the `Rule ▾` menu being cut off in the mail view

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

Todo `a62dffd2-029e-49b5-a8e6-70826db93104`: "mail > add to existing rule is behind mail list panel."

## Context

`MailRuleMenu.vue` offers "New rule from this mail" and "Add to existing rule …" in a dropdown (`.menu-pop`, `position: absolute; left: 0; min-width: 220px`) in the mail header toolbar.
The toolbar sits at the right end of `.mail-message`, which is an `overflow-y: auto` scroll column (`styles/main.scss`, shared rule for `.mail-folders, .mail-list, .mail-message`).
Anchored at the left edge of the `Rule ▾` button, the dropdown extends to the right and the scroll column clips it.
The "Add to existing rule …" item is cut off at the pane edge, which is what the todo describes.
The dialog itself (`.modal-backdrop`, fixed, `z-index: 50`) is fine, and Playwright confirms it is topmost at 1280, 900, 700 and 390 px.

Reproduced with Playwright screenshots at 700 px and 390 px: the popup is about 184 px wide instead of its 220 px `min-width`, and it ends exactly at the pane edge.

## Changes

1. `frontend/src/components/MailRuleMenu.vue`: give the popup the modifier class `end` (`class="menu-pop end"`).
2. `frontend/src/styles/main.scss`, `.menu-pop`: add `&.end { left: auto; right: 0; }`, and `max-width: calc(100vw - 32px)` so no menu is ever wider than the screen.
   Right-aligned, the popup grows leftwards into the toolbar, where there is room (the `Rule ▾` button's right edge is at 262 px on a 390 px phone).
   `Move ▾` stays left-aligned, since it is further left and right-aligning it would clip it on the left on a phone.
3. `frontend/e2e/mail.spec.ts`: keep the draft test as the regression test, in a stricter form.
   It loops over widths 1280, 900, 700 and 390 and, with the menu open, asserts that the popup's bounding box lies fully inside the viewport and inside the `.mail-message` box.
   Then it opens "Add to existing rule …" and asserts the `.modal` is topmost (`elementFromPoint`).
   It must fail before the SCSS change and pass after. The `test-results/` screenshots calls are removed.
4. `CLAUDE.md`: one sentence in the "Mail view" bullet that header menus are anchored with `.menu-pop` (`.end` for the right-hand `Rule ▾`) because the scroll column clips them.

## Verification

- `cd frontend && yarn playwright test e2e/mail.spec.ts` (new test red first, then green), then `yarn test:e2e`, `yarn test`, `yarn lint`, `yarn build`.
- `uv run pytest` once for the full suite (no backend change expected).
- Look at the 390 px and 700 px screenshots once more to confirm the popup is fully visible.

## Leftovers

The sync_todo MCP server did not connect (`CONNECTION_CLOSED`) and `sync_todos.py` found no `SYNC_TODO_MCP_URL`, so `complete_todo` on CalDAV cannot run from here.
After implementing I will tick the checkbox locally and report that the CalDAV completion and sync are still to do.
