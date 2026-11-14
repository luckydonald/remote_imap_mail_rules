# Allow using a template in a template, and set `!var` there

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

Todo `4a381196-a77e-45e6-a9d3-a9cbc0418140`: "Allow using a template in a template, and to set `!var` there. The default name for `!var` shall be the parent's var."

## Context

The model already supports nesting: `used_variables` / `Template.concrete` (backend `rules/models.py`) and `neededVariables` / `expandRules` (frontend `model/validate.ts`, `model/yaml-io.ts`) resolve a use inside a template, and `test_nested_template_gets_outer_variable` covers it.
What is missing is the editor.
`TemplateUseEditor.vue` takes every variable as plain text (`parseValue`), so inside a template the user cannot bind a nested variable to an outer variable (`{var: topic}`, `!var topic`) without editing the YAML.
Also a new use inside a template starts with `Object.keys(templates)[0]`, which can be the template being edited, a self reference.

## Changes

1. `components/FieldValue.vue`: new optional prop `varName` (default `''`), the name a freshly switched `!var` gets: `toggle()` emits `{ var: props.varName }` instead of `{ var: '' }`.
   Switching back emits `fallback`; `undefined` is allowed as fallback.
2. `components/condition/TemplateUseEditor.vue`: wrap each variable input in `FieldValue` with `:model-value="model.variables[name]"`, `:var-name="name"` (the nested template's own variable name is the default for the parent's var, per the todo) and `:fallback="undefined"`.
   Updating with a `Var` stores it, updating with `undefined` deletes the key (like an empty input does now), the text input still uses `parseValue` / `showValue`.
   The `var` toggle only shows with `ALLOW_VARS`, so uses in rules are unchanged.
   The placeholder (`default: …` / `required`) stays on the text input.
3. Self reference guard: the template editor (`TemplatesView.vue`) provides the name of the template being edited (new injection key `CURRENT_TEMPLATE` next to `ALLOW_VARS` in `model/context.ts`).
   `TemplateUseEditor` lists as options only templates that do not lead back to it (a small `reaches(file, from, target)` helper in `model/validate.ts`), and `ConditionNode.changeType` passes the filtered names to `newExpression`.
   `validateRules` reports a template cycle as a problem (`template \`a\` uses itself`), because the backend would otherwise hit a recursion while the frontend expansion silently stops.
4. Backend: no model change needed; add tests.
5. Update `CLAUDE.md` (Templates decision): nested uses are edited with a `var` toggle per variable, default name = the nested variable's name, cycles are refused.

## Tests

- `tests/test_rules_templates.py`: nested use where the outer template gives a default for the passed variable; a nested use with a missing outer variable raises.
- `frontend/src/__tests__/components.spec.ts`: inside a template (provide `ALLOW_VARS`) the toggle on a nested use's variable sets `{ var: '<variable name>' }`, renaming it works, toggling back deletes the key; in a rule no toggle shows; the select does not offer the template being edited.
- `frontend/src/__tests__/validate.spec.ts`: cycle problem; nested use with `!var` satisfied.
- `frontend/src/__tests__/yaml-io` spec: `!var` inside a nested use's `variables` round trips.
- e2e: not needed, the behaviour is component level.

## Verification

`uv run pytest`, `cd frontend && yarn test && yarn lint && yarn build`; `yarn test:e2e` once for the templates screen.
