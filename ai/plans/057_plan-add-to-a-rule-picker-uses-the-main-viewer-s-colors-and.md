# Plan: "Add to a rule" picker uses the main viewer's colors and AND/OR/NOT formatting

## Context

Todo `6e1d2a66`: the graphical picker in the "Add to a rule" dialog (`RuleInsertNode.vue`) shows groups as plain text ("all of 3") with a neutral grey left border.
The main editor (`ConditionNode.vue`) colors groups by type (`--node-all` blue, `--node-any` orange, `--node-not` magenta, via `.node.node-<type>` in `styles/main.scss`) and labels them "All of (AND)", "Any of (OR)", "Not" (`typeLabels` in `model/catalog.ts`).
The picker should look the same, but keep its clean look: one-line leaves and big `+ Insert here` areas.
Merging the two components with slots is not done, since the editor node carries a lot of editing UI the picker does not want.
The colors and labels are shared instead, so they cannot drift.

## Changes

- `frontend/src/components/RuleInsertNode.vue`
  - Group root gets the classes `node` is *not* reused (its padding, margin and panel are editor specific); instead add `node-all` / `node-any` / `node-not` style hooks `insert-<type>` that set `border-left-color` from the same CSS variables.
  - `.insert-head` shows a badge with `typeLabels[expr.type]` for groups (plus the child count for all/any, e.g. `All of (AND) · 3`), colored with the type variable, instead of `describeExpression` for groups.
  - Leaves keep `describeExpression`; a `template` leaf gets the `--ok` border like `.node-template`.
- `frontend/src/styles/main.scss` (`.insert-group`, `.insert-head`, `.insert-row`)
  - Nested `.insert-group` keeps `border-left: 4px solid var(--border)` as default and overrides it per `.insert-all`, `.insert-any`, `.insert-not`, `.insert-template`, mirroring `.node` (same width 4px, radius 8px, panel background).
  - `.insert-head` text colored by the type variable (works in the dark scheme, since the variables already switch).
- `describeExpression` in `model/fill-from-mail.ts` is untouched (other callers use it).

## Tests

- `frontend/src/__tests__/rule-insert-picker.spec.ts`: groups show the `typeLabels` text and have the `insert-all` / `insert-any` / `insert-not` class; leaves still show the one-liner.
- Existing `insert-point` counts and aria-labels stay unchanged (asserted by `rule-index.spec.ts` and the e2e in `mail.spec.ts`).
- `yarn test`, `yarn lint`, `yarn build`, and the `mail.spec.ts` e2e (`yarn test:e2e`, Chromium and `webkit-ipad`).

## Docs

One sentence in the `CLAUDE.md` "Add to existing rule" description: the picker's group boxes use the editor's `--node-*` colors and `typeLabels`.

## Verification

Run the e2e mail spec, and open the dialog in Playwright with a rule holding all/any/not groups to check the border colors against the editor's.
