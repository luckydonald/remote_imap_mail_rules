# Rule templates (mini macros) for the rule file

## Context

Writing anonaddy rules is tedious, because every sender needs the same `all` of "from address equals X" and "from name endswith Y" block.
The idea is a root level `templates:` mapping with replaceable fields, instantiated from a rule via the native YAML `&anchor` / `*alias` system.
`rules/rules.example.yml` is the first sketch, and it has two problems that the design below fixes:

- `- *template.anonaddy-forward` followed by a sibling `variables:` key is invalid YAML, an alias cannot take siblings.
  The YAML way to "alias and override" is the merge key `<<: *alias`.
- `!!variable` is the `tag:yaml.org,2002:` secondary handle, reserved for the YAML spec.
  A custom tag is written `!var` with a single `!`.

The template pieces must be real pydantic types, so `schemas/rules.schema.json` validates the file before any replacement happens.

## File syntax

```yaml
templates:
  anonaddy-forward: &template.anonaddy-forward
    type: template
    defaults:
      from_name: " 'notifications at github.com'"   # optional, an instance may override
    content:
      type: all
      conditions:
        - {type: address, field: from, part: address, operator: equals, value: !var from_address}
        - {type: address, field: from, part: name, operator: endswith, value: {var: from_name}}

rules:
  - name: ...
    when:
      type: any
      conditions:
        - <<: *template.anonaddy-forward
          variables:
            from_address: "github.com-example@luckydonald.de"
```

- The marker is `{var: name}` (a pydantic model, schema-valid).
  The YAML tag `!var name` is loader sugar producing exactly that dict.
- The merge key copies `type`, `defaults` and `content` into the instance, the instance adds `variables`.
  Shallow merge replaces whole keys, so defaults live in `defaults` and overrides in `variables` (renamed from the sketch, where both were `variables`).
- Names under `templates:` only document and key the definitions, the link between definition and use is the YAML anchor.

## Models (`rules/models.py`)

- `type Templatable[T] = T | Var`, with `class Var(Strict): var: str`.
- Applied to every value-bearing field of the conditions and the plain fields of `Rule` and `Location` and of the actions: `field`, `part`, `operator`, `value`, `case_sensitive`, `quantifier`, header `name`, `folder`, `account_id`, `recursive`, `enabled`.
  Not applied to the `type` discriminators, and not to the `locations` / `actions` / `conditions` lists as a whole.
- Existing `check_value` validators return early when the value (or the operator) is a `Var`, they run for real on the concrete re-validation.
- `Template[C]` generic with `type: Literal["template"]`, `defaults: dict[str, Any]`, `variables: dict[str, Any]`, `content: C`.
  Used as `Template[Expression]` and added to the `Expression` union, so `Templatable[Expression]` = `Template[Expression] | Expression` falls out for every expression slot.
  If pydantic cannot do the recursive generic with forward refs cleanly, fall back to a plain non-generic `TemplateInstance` with `content: Expression`.
- Root `RuleFile.templates: dict[str, TemplateDefinition]`, where `TemplateDefinition` is the same shape without the usage check, so unfilled variables are fine there.
- Usage check as a normal pydantic `model_validator` on the instance class: every `Var` found in `content` needs a value in `variables` or `defaults`, and `variables` may not contain names the content never uses (typo guard).
  The error message carries the variable name, the rule name is added by `Rule`'s validation context path.
- Nested templates work, because a variable value may itself be a `Var` that the outer instance binds.

## `.concrete()`

- New base class `Concrete(Strict)` (all models inherit it) with `def concrete(self, variables: Mapping[str, Any] | None = None) -> Self`.
- Default implementation: walk the fields, replace a `Var` by `variables[name]`, recurse into nested `Concrete` values and lists, then `type(self).model_validate(...)` on the rebuilt data so type coercion and the cross-field validators run on the substituted values.
  A missing binding raises `ValueError`.
- `Template.concrete(variables)` returns `content.concrete({**defaults, **resolved_variables})`, so a template node is replaced by its content, and the parent re-validation then sees only plain expressions.
- `RuleFile.concrete()` additionally drops `templates`.
- The evaluator side keeps working on the result.
  `evaluate.py` and `extract.py` read the widened fields through narrowing (`assert not isinstance(x, Var)` or a `cast`) at the few places they touch them, to be listed when implementing.

## Loading

- `rules/loader.py:10`: `parse_rules` uses a `yaml.SafeLoader` subclass (`RuleLoader`, in `rules/templates.py`) that turns `!var x` into `{"var": "x"}`, then `RuleFile.model_validate(...).concrete()`.
- `demo.py` and `matching.py` call `load_rules` today, so they get concrete rules without changes.

## Other changes

- `schemas/rules.schema.json`: regenerate with `uv run python -m remote_imap_mail_rules.rules.schema --write-schema`.
- `rules/rules.example.yml`: rewrite to the valid syntax above, keep one unrolled rule next to the template one as before/after.
- `CLAUDE.md`: a "Templates" bullet under Decisions, `templates.py` in Layout, and `rules/models.py` mention of `Templatable` / `.concrete()`.

## Verification

- New `tests/test_rules_templates.py`: a templated rule `.concrete()` equals the hand written rule, defaults and override, nested template, `{var: x}` and `!var x` equivalence, `Var` on a number field and on an operator, missing variable (fails at `model_validate`, not only at `concrete`), unknown variable, template definition under `templates:` with unfilled variables is valid, `RuleFile.concrete()` has no `Var` or `Template` left anywhere.
- Existing tests: `uv run pytest` (includes the schema `--check` test), and `uv run python -m remote_imap_mail_rules.rules.schema --check`.
- Validate `rules/rules.example.yml` against the regenerated schema (the sketch must pass before replacement) and through `load_rules`, then `demo.py --no-streamer-mode` if an account is configured.
