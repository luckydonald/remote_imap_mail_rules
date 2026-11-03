# Plan: Vue frontend for the rules file

## Context

The backend can parse, validate and run a YAML rules file (`rules/models.py`, `schemas/rules.schema.json`), but rules can only be written by hand.
`ai/initial.md` lists a "rule editor" and a "vue js frontend" as goals, and there is no FastAPI server yet.
This builds the first version as a standalone, file-based editor in `frontend/`: open or paste a rules YAML, edit it visually, validate it live, download or copy the YAML.
Server load/save can be added later without reshaping the editor.
Decisions from the user: standalone and file-based, and the scope includes editing templates.

## Stack and conventions

- Vue 3, `<script setup lang="ts">`, TypeScript, SCSS, Vite, pnpm (v10+ present, node 24).
- Pinia is not needed, one `reactive` store composable is enough.
- Libraries: `yaml` (eemeli, preserves anchors, aliases and custom tags such as `!var`), `ajv` (validate against `schemas/rules.schema.json`, imported from the repo root through a Vite alias, never copied or edited).
- Tests with Vitest + `@vue/test-utils`, as `/code-style` requires frontend tests.
- Follow `.claude/skills/code-style/references/{ts,vue,md}.md`.
  Prose in new `.md` files is wrapped at sentence ends.
- `frontend/` gets its own `package.json`, `pnpm-lock.yaml`, `.gitignore` for `node_modules` and `dist`.
- Add the frontend to the `CLAUDE.md` Layout section and mention how to run it in `README.md`.

## Files (under `frontend/`)

- `src/model/types.ts`: TS types mirroring the rule file: `Expression` union on `type` (`all`, `any`, `not`, `text`, `address`, `header`, `number`, `date`, `bool`, `presence`, `template`), `Location`, `Action`, `Rule`, `TemplateDef`, `RuleFile`, and `Var = {var: string}`.
- `src/model/catalog.ts`: field lists per type (from `rules/fields.py`), operators per type, address parts, quantifiers, action types, defaults for a new node of each type.
  Field and operator lists are read from the JSON schema enums where possible so they cannot drift, with a test that compares them.
- `src/model/yaml-io.ts`:
  - `parseRules(text)` uses `yaml` `parseDocument`, with a `!var name` tag mapped to `{var: name}`, and `<<: *anchor` merge keys resolved into plain `template` nodes.
  - Internal model for a template use is `{type: "template", ref: "<name>", variables}` rather than the expanded copy.
  - `stringifyRules(file)` writes `templates:` with anchors (`&template-name`), uses as `<<: *template-name` plus `variables`, `!var name` for variables, and keeps the `# yaml-language-server: $schema=` first line.
  - Round-trip test against `rules/example.yml` and `rules/rules.example.yml`.
- `src/model/validate.ts`: ajv validation of the serialized, un-expanded object, returning errors with a JSON path so the UI can mark the node.
  Extra check for template uses: every variable bound, none unknown (mirrors `Template.check_variables`).
- `src/model/store.ts`: `useRulesStore()` holding the `RuleFile`, selected rule, dirty flag, validation errors (recomputed on change), undo/redo stack of snapshots.
- `src/components/`:
  - `AppShell.vue`: header (Open, Paste, New, Download, Copy YAML, Undo/Redo, error count), left rule list, right editor, bottom/side YAML preview tab.
  - `RuleList.vue`: add, duplicate, delete, reorder (drag or up/down), enabled toggle.
  - `RuleEditor.vue`: name, enabled, `LocationsEditor`, `ConditionNode` tree, `ActionsEditor`.
  - `LocationsEditor.vue`: `account_id` (UUID), `folder` (default `INBOX`), `recursive`.
  - `ConditionNode.vue`: recursive; chooses the sub-editor by `type`, with "wrap in all/any/not", "remove", "replace by template".
  - `condition/`: `GroupEditor.vue` (all/any/not), `TextEditor.vue`, `AddressEditor.vue` (with `part`), `HeaderEditor.vue`, `NumberEditor.vue` (`between` shows two inputs), `DateEditor.vue` (absolute datetime or relative duration `7d`, `between` pair), `BoolEditor.vue`, `PresenceEditor.vue`, `TemplateUseEditor.vue`.
  - `FieldValue.vue`: wraps any value input with a "use variable" toggle, so every `Templatable` field can switch between a literal and `!var name`, offering variables declared by the enclosing template.
  - `ActionsEditor.vue`: `move` (`folder`, optional `account_id`), `mark_read`, `mark_unread`, `flag`, `keyword`.
  - `TemplatesView.vue`: list of template definitions, each with name (anchor), `defaults` key/value editor and a `content` `ConditionNode` tree where `FieldValue` offers variables.
    Shows which rules use each template; deleting a used template is blocked with a message.
  - `YamlPreview.vue`: read-only generated YAML plus an "edit raw" mode that re-parses on apply and shows parse errors.
- `src/styles/`: SCSS tokens with light and dark `prefers-color-scheme`, mobile-friendly layout.
- `tests/`: `yaml-io.spec.ts` (round trip, `!var`, anchors), `validate.spec.ts`, `catalog.spec.ts` (enums match the schema), `store.spec.ts` (undo/redo), component specs for `ConditionNode` (nesting, switching type) and `FieldValue`.

## Behaviour notes taken from `CLAUDE.md`

- Operators offered per type: text `equals contains startswith endswith regex glob in` (`in` takes a list), number and date `eq ne lt gt gte lte between`, quantifier `any/all/none` only for multi-valued fields.
- `case_sensitive` toggle on text, address and header conditions.
- Date value editor mirrors the discriminated union on `relative`: naive datetime means UTC, relative units `s m h d w`.
- `presence` has exactly one of `field` / `header`.
- Hint texts for the pitfalls: a missing field makes every operator false, even `ne`, and `date_received lt 7d` means older than a week.
- Folder names are shown as-is (modified UTF-7), `actions` are labelled "parsed only, not executed yet".

## Build order

1. Scaffold Vite + Vue + TS + SCSS + Vitest in `frontend/`, alias to `../schemas/rules.schema.json`.
2. Types, catalog, `yaml-io` with round-trip tests, then validation.
3. Store with undo/redo.
4. Rule list, rule editor, locations, actions.
5. Condition tree and all condition editors.
6. Templates view, `FieldValue` variable toggle, template use editor.
7. YAML preview and raw edit, open, download, copy.
8. Docs (`CLAUDE.md` layout, `README.md`, `ai/initial.md` status), then commits per task in the `/commit-with-lplp-style` pattern.

## Verification

- `cd frontend && pnpm install && pnpm test && pnpm vue-tsc --noEmit && pnpm build`.
- Round trip: load `rules/rules.example.yml` in the editor, download without edits, then `uv run python -c "from remote_imap_mail_rules.rules.loader import load_rules; ..."` (or `uv run pytest`) on the output and compare the resolved rules with the original's.
- Create a rule from scratch in the editor, including a nested `all > any > not`, a template with a variable and a use, then check the downloaded file passes the backend loader and the schema (`uv run python -m remote_imap_mail_rules.rules.schema --check` stays green, schema is unchanged).
- Run `pnpm dev` and drive it in the browser (Chrome tools): open the example file, edit, see validation errors for an invalid regex-free case such as an unbound template variable, undo/redo, light and dark mode, phone width.
