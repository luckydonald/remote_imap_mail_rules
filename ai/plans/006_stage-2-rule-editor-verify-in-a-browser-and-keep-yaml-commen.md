# Stage 2 (rule editor): verify in a browser and keep YAML comments

**Commit style:** Skill `/commit-with-lplp-style` is active, auto-commit following it for this implementation.

## Context

Stage 2 of `ai/initial.md` has four `[?]` items (open/drop/edit/download, live validation, undo/redo, light/dark) that are only covered by Vitest, the type check and the build, never looked at in a browser.
The fifth item, keeping comments in the YML when saving, is not built: `stringifyRules()` in `frontend/src/model/yaml-io.ts` creates a fresh `Document`, so every comment is lost.
Goal: turn all `[?]` into `[x]` with evidence, and implement comment preservation.

## Tasks (one commit each)

1. **Browser check.**
   - Run `cd frontend && yarn dev`, drive it with the Chrome tools against `rules/rules.example.yml` and `rules/example.yml`.
   - Walk through: open and drop a file, edit a rule, location, condition tree, action and template, see the live problems list react, undo/redo, toggle light/dark, download and copy.
   - Fix what is broken, each fix with a Vitest case where it is testable (`src/__tests__/components.spec.ts`, `store.spec.ts`).
   - Also run `yarn test`, `yarn build` and `yarn lint` first as the baseline.

2. **Keep comments when saving.**
   - `parseRules()` keeps the parsed `Document` next to the model (in the store: `sourceDoc`, reset on `load`).
   - `stringifyRules(file, sourceDoc?)` builds the new document as today, then copies comments over from the source document by path: `commentBefore`, `comment` and `spaceBefore` on matching nodes.
   - Paths use stable keys: map keys, and for the `rules` sequence the rule `name` (fallback to index), so moving, duplicating or deleting a rule keeps the comments of the others.
   - Nodes that no longer exist drop their comments; new nodes have none.
   - Top-of-file comment and the `yaml-language-server` header stay as they are now.
   - Tests in `yaml-io.spec.ts`: comments survive a parse/stringify round trip, survive editing a value, survive reordering rules, and a removed rule takes its comment away.
   - Update `CLAUDE.md` ("comments are lost") and the "Status so far" section of `ai/initial.md`.

3. **Docs.** Tick the `[?]` items in `ai/initial.md` stage 2 that were verified, drop the "Not looked at in a browser yet" and "Comments … are not kept" lines, and set the stage status to done if everything passes.
   Prose wraps at sentence ends per the md style guide.

## Verification

- `uv run pytest` is unaffected, but run `cd frontend && yarn test && yarn build && yarn lint` after each task.
- Browser: load `rules/rules.example.yml` with comments added, edit, download, and diff the downloaded file against the original; only intended changes may differ and comments must remain.
- `uv run python -m remote_imap_mail_rules.rules.schema --check` stays green (no schema change expected).
