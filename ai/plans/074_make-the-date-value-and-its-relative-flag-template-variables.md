# Make the date value and its `relative` flag template variables

**Commit style:** Skill `/commit-with-lplp-style` is active, auto-commit following it for this implementation.

Todo `7d708b81-44a5-4f49-bfcc-a060343cbb47`.

## Context

A `date` condition can already be a `!var` as a whole, or its `field` and `operator` can be.
The time value itself, `{relative: false, value: "2026-11-18T08:54:08"}`, cannot hold a variable inside: neither its `value` nor its `relative`.
The todo wants both to be variable-able, in YAML and from the GUI, with a browser test that builds such a template, clicks `var` on the date, and uses the template somewhere.

## Findings

- `rules/values.py` has `AbsoluteTime` and `RelativeDuration` as plain `BaseModel`s, `TimeValue` is a union discriminated on the literal `relative`.
- `DateCondition.value` in `rules/models.py` is `Templatable[TimeValue | tuple[TimeValue, TimeValue], V]`, so only the whole value (or the whole pair) can be a `Var`.
- `substitute` / `concretize` only descend into `Concrete` models, `used_variables` into `Strict` ones, so the time models must become `Concrete` (a `Strict`) to be walked.
- `evaluate.resolve_time` and the rest only see the concrete form, so the evaluator does not change.
- Frontend: `TimeInput.vue` edits one `TimeValue`, `DateEditor.vue` wraps the whole value in a `FieldValue`, `model/types.ts` types `TimeValue` as the two literal shapes.

## Backend

- In `rules/values.py` make the time models generic in `V = Var` and subclass `Concrete` (move `Strict`, `Var`, `Templatable` use as needed without an import cycle, for example by moving `Strict`, `Var`, `Templatable` and `Concrete` into a small `rules/base.py` re-exported by `models.py`).
  - `AbsoluteTime`: `relative: Templatable[Literal[False], V] = False`, `value: Templatable[datetime, V]`.
  - `RelativeDuration`: `relative: Templatable[Literal[True], V]`, `value: Templatable[str with the duration pattern, V]`, the normalizing validator skips a `Var`.
  - New `VariableTime`: `relative: V` (a `Var`), `value: Templatable[datetime | str, V]`; its `concrete()` substitutes the fields and validates the result as `AbsoluteTime | RelativeDuration`, so the evaluator never sees it.
  - `TimeValue[V] = AbsoluteTime[V] | RelativeDuration[V] | VariableTime[V]` as a plain (smart) union, since a `Var` in the discriminator field cannot be a discriminated union. Exactly one member validates for any input.
- `DateCondition.value` keeps `Templatable[TimeValue[V] | tuple[TimeValue[V], TimeValue[V]], V]`; `check_value` stays.
- A bad combination after substitution (a `relative: true` with a datetime, a duration that does not match) fails in the final validation and reaches the user as a normal 422 with the message.
- Regenerate `schemas/rules.schema.json` with `uv run python -m remote_imap_mail_rules.rules.schema --write-schema`.
- Tests in `tests/test_rules_templates.py` (or the existing template test file) and `tests/test_rules_evaluate.py`:
  - `value: !var` inside an absolute and a relative time, with a default and with `variables` of a use.
  - `relative: !var` with a `value` var, the result being an `AbsoluteTime` for `false` and a `RelativeDuration` for `true`.
  - Mixed case: `relative: false` fixed and `value` a var, in a `between` pair.
  - Errors: an unbound variable, a var that gives a wrong shape (`relative: true` with a datetime).
  - `used_variables` / unknown-variable check sees the new vars.

## Frontend

- `model/types.ts`: `TimeValue` becomes `{ relative: Templatable<boolean>; value: Templatable<string> }` (the three shapes as a union where it helps narrowing).
- `TimeInput.vue`: when template variables are allowed (`ALLOW_VARS`), wrap the kind select in a `FieldValue` for `relative` (fallback `true`) and the text or datetime input in a `FieldValue` for `value` (fallback depends on the kind, `7d` or now).
  - When `relative` is a var the value input has no kind to choose a widget by, so show a plain text input for the value var (its `FieldValue` is already in var mode only when the user picked it) and a fixed value as text.
  - Switching the kind keeps a var `value`, otherwise it resets the value as now.
- `DateEditor.vue`: the outer `FieldValue` for the whole value stays, the new buttons are inside `TimeInput`; default var names follow the field (`value`, `relative`) via `varName`.
- `yaml-io.ts` already keeps `!var` anywhere, so nothing changes there; check with a round-trip test.
- `validate.ts` / the template variable check must find vars inside the time value: extend the walker if it only looks at top-level fields of a condition.
- `fill-from-mail.ts`, `template-match.ts` and `catalog.ts` still build only concrete time values, check that `template-match.ts` treats a var time as a wildcard like other var fields.
- Vitest: yaml round trip with `!var` in `relative` and `value`, `validate` with an unbound var, `TimeInput` emits the var shape.
- Playwright e2e (`e2e/`, mocked `/api`, in the existing template spec): create a template with a date condition, click `var` on the date value and on `relative`, name them, check the YAML view shows `!var`, add a use of the template in a rule, fill the variables, and check the expanded YAML or the validation shows the concrete date.

## Docs

- `CLAUDE.md`: in Templates (Decisions) note that the time value's `value` and `relative` can be variables, `VariableTime`, and that a `Var` `relative` is why `TimeValue` is no longer a discriminated union.

## Verification

- `uv run pytest`, `uv run python -m remote_imap_mail_rules.rules.schema --check`.
- `cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`.
- No server, mailbox or live account is touched.
