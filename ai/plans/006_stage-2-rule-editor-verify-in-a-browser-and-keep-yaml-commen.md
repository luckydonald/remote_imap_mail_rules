# Stage 2 (rule editor): verify in a browser and keep YAML comments

**Commit style:** Skill `/commit-with-lplp-style` is active, auto-commit following it for this implementation.

## Context

Stage 2 of `ai/initial.md` has four `[?]` items (open/drop/edit/download, live validation, undo/redo, light/dark) that are only covered by Vitest, the type check and the build, never looked at in a browser.
The fifth item, keeping comments in the YML when saving, is not built: `stringifyRules()` in `frontend/src/model/yaml-io.ts` creates a fresh `Document`, so every comment is lost.
Goal: turn all `[?]` into `[x]` with evidence, and implement comment preservation.

## Tasks (one commit each)

1. **Playwright end-to-end tests (no Chrome tooling).**
   - Add `@playwright/test` as a dev dependency in `frontend/`, a `playwright.config.ts` (webServer: `yarn dev`, Chromium only), `e2e/` for the specs, and a `test:e2e` script.
   - Keep Vitest away from `e2e/` (exclude it in `vitest.config.ts`), and include the new config in the tsconfig/lint setup the way `create-vue` does.
   - Specs load `rules/rules.example.yml` and `rules/example.yml` and cover: open via file input and drop, edit a rule, location, condition tree, action and template, the live problems list reacting, undo/redo, light/dark toggle (`prefers-color-scheme` emulation plus the toggle), and download/copy of the YAML.
   - Fix what the tests expose, each fix with a Vitest case where it is testable (`src/__tests__/components.spec.ts`, `store.spec.ts`).
   - Run `yarn test`, `yarn build` and `yarn lint` first as the baseline.

2. **Keep comments when saving.**
   - `parseRules()` keeps the parsed `Document` next to the model (in the store: `sourceDoc`, reset on `load`).
   - `stringifyRules(file, sourceDoc?)` builds the new document as today, then copies comments over from the source document by path: `commentBefore`, `comment` and `spaceBefore` on matching nodes.
   - Paths use stable keys: map keys, and for the `rules` sequence the rule `name` (fallback to index), so moving, duplicating or deleting a rule keeps the comments of the others.
   - Nodes that no longer exist drop their comments; new nodes have none.
   - Top-of-file comment and the `yaml-language-server` header stay as they are now.
   - Tests in `yaml-io.spec.ts`: comments survive a parse/stringify round trip, survive editing a value, survive reordering rules, and a removed rule takes its comment away.
   - Update `CLAUDE.md` ("comments are lost") and the "Status so far" section of `ai/initial.md`.

3. **Docs.** Tick the `[?]` items in `ai/initial.md` stage 2 that the e2e tests verified, replace the "Not looked at in a browser yet" line with a note about the Playwright tests, drop the "Comments … are not kept" lines, and set the stage status to done if everything passes.
   Prose wraps at sentence ends per the md style guide.

## Verification

- `uv run pytest` is unaffected, but run `cd frontend && yarn test && yarn build && yarn lint` after each task.
- `yarn test:e2e` passes; one e2e case loads a file with comments, edits, downloads, and compares against the original: only intended changes may differ and comments must remain.
- `uv run python -m remote_imap_mail_rules.rules.schema --check` stays green (no schema change expected).
