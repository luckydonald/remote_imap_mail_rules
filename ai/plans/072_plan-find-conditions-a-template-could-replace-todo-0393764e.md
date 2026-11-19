# Plan: Find conditions a template could replace (todo 0393764e)

**Commit style:** Skill `/commit-with-lplp-style` is active, auto-commit following it for this implementation.

## Context

Rules often repeat a condition that a template already describes.
The todo asks for a check, once per day, that finds such conditions, with a green badge on the template in the sidebar and a green tag on the condition in the rules.
The user added: if the check is light enough, also run it when or after saving.
It is frontend only, no server or schema change.
The sidebar has one `Templates` entry (`RuleList.vue`), the per-template list is `TemplatesView.vue`, so the sidebar badge shows the total count and `TemplatesView` shows the count per template.

## Matching (pure, new `frontend/src/model/template-match.ts`)

- `matchTemplate(content, candidate, defaults): Record<string, unknown> | null`: walks both expressions in parallel.
  Where the template holds a `{var: x}`, bind x to the candidate's value; a repeated variable must bind equal values (deep equal).
  Everything else must be deep equal, so group order and `type` must agree.
  A variable whose bound value equals its default is left out of the result.
  A nested `TemplateUse` in the content matches a candidate use with the same `ref`, and its `variables` are matched like fields.
- `findReplaceable(file): TemplateHint[]`: for every rule's `when` (and every other template's content), visit every subtree that is not already a template use and try each template.
  Skip a template matching inside its own content (and anything `leadsTo` it, reusing `usableTemplates` / `leadsTo` from `validate.ts`, so no cycle is suggested).
  Skip templates whose content is a bare leaf with no variable and no other structure only if it would match everything (a template with zero fixed fields); otherwise a hint is `{template, rule | templateName, path, variables}`, path being the child index path like `appendCondition` uses.
  Prefer the largest matching subtree and do not report its children again.
- Cost is one tree walk per template per subtree, linear for realistic files, so it is light enough to run after every save.

## When it runs (`frontend/src/model/store/template-hints.ts`, spread in `store/index.ts`)

- New plain function `useTemplateHints(rules)` returning `templateHints` (ref), `hintsFor(template)`, `hintAt(rule, path)` and `refreshTemplateHints()`.
  No second store, per the one central store rule.
- Refresh triggers: after the file is loaded, after `markSaved` (the save, server file or the YAML view's `Save to …`), and once per day: the check date lives in localStorage `template-hints-checked` as a `YYYY-MM-DD`, a `shouldCheck(last, now = new Date())` pure helper (injectable clock like `offline/cache.ts`), evaluated at start and when the tab becomes visible, wrapped in try/catch like `prefs.ts`.
- Between refreshes the hints are a snapshot (they can go stale while editing, which is why the Save refresh matters); a hint whose path no longer holds the same expression is dropped by `hintAt` comparing a JSON key of the node.
- The daily run and the save run are the same function, so the todo's wording and the user's addition share one code path.

## UI

- `RuleList.vue`: next to the count badge of `Templates`, a `badge ok` with the number of hints, `title` "n conditions could use a template".
- `TemplatesView.vue`: in each template's header a `badge ok` with its hint count.
- `ConditionNode.vue`: in the `node-bar` before the spacer, `<span class="badge ok">` "use template X" when `hintAt` finds one for this node, not shown for a template use or inside the template itself (`CURRENT_TEMPLATE`).
  A click on the tag replaces the condition by `{type: 'template', ref, variables}` in one undo step, after the same confirm-free pattern as `Unwrap`.
  Needs a way for the node to know its rule and path: check how `GroupEditor.vue` passes the path today, else add a `path` prop.
- Style: reuse `.badge.ok` from `styles/main.scss`.
- Offline: purely local, works offline.

## Tests

- `src/__tests__/template-match.spec.ts`: exact match, bound variable, repeated variable with different values (no match), default left out, nested use, no suggestion inside the template itself or through a cycle, largest subtree wins.
- `src/__tests__/template-hints.spec.ts`: `shouldCheck` with an injected date, store refresh after `markSaved`, stale hint dropped.
- Component test in `components.spec.ts`: the tag shows on a matching condition, click replaces it with a use, the sidebar badge count.
- A Playwright check in `e2e/` for the green tag and the sidebar badge, with the `/api` proxy closed as the other specs do.

## Docs

Add one line in `CLAUDE.md` frontend section about `template-match.ts` / `template-hints.ts` and the daily + after-save refresh.

## Verification

`cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`, then `uv run pytest` for the untouched backend.
