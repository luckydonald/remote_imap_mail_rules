# Rule templates (mini macros) for the rule file

## Context

Writing anonaddy rules is tedious, because every sender needs the same `all` of "from address equals X" and "from name endswith Y" block.
The idea is a root level `templates:` mapping with replaceable fields, instantiated from a rule via the native YAML `&anchor` / `*alias` system.
`rules/rules.example.yml` is the first sketch, and it has two problems that the design below fixes:

- `- *template.anonaddy-forward` followed by a sibling `variables:` key is invalid YAML, an alias cannot take siblings.
  The YAML way to "alias and override" is the merge key `<<: *alias`.
- `!!variable` is the `tag:yaml.org,2002:` secondary handle, which is reserved for the YAML spec.
  A custom tag is written `!var` with a single `!`.

## Design

Expansion is a pure pre-processing step on the parsed YAML data in `loader.py`, before `RuleFile.model_validate`.
The evaluator, `matching.py` and the pydantic condition models stay untouched, they never see a template.

Rule file syntax:

```yaml
templates:
  anonaddy-forward: &template.anonaddy-forward
    type: template
    defaults:
      from_name: " 'notifications at github.com'"   # optional defaults, an instance may override them
    content:
      type: all
      conditions:
        - {type: address, field: from, part: address, operator: equals, value: !var from_address}
        - {type: address, field: from, part: name, operator: endswith, value: !var from_name}

rules:
  - name: ...
    when:
      type: any
      conditions:
        - <<: *template.anonaddy-forward
          variables:
            from_address: "github.com-example@luckydonald.de"
```

- `!var name` is a custom tag, a loader subclass of `yaml.SafeLoader` turns it into a `Var(name)` marker object.
  It works at any scalar position, so numbers and bools can be templated too, as validation happens after expansion.
- A node with `type: template` is an instance.
  The merge key copies the template's `type`, `defaults` and `content` into it, the instance adds `variables`.
  Shallow merge replaces whole keys, which is why the defaults live in `defaults` and the overrides in `variables` (a rename from the sketch, where both were `variables`).
- Expansion walks the data tree.
  Every `type: template` node becomes a deep copy of `content` with each `Var` replaced by `variables[name]`, falling back to `defaults[name]`.
  Replaced content is walked again, so templates can use templates.
- Errors, all raised as `ValueError` naming the rule: a variable without value and default, a `variables` key the template never uses (typo guard), a `Var` left outside any template instance, a cycle (depth cap).
- The `templates:` mapping itself is dropped from the data after expansion, and an unused template is fine.
  Names under `templates:` are only documentation and the schema key, the link is the YAML anchor.

## Changes

- `src/remote_imap_mail_rules/rules/templates.py` (new): `Var`, `RuleLoader` (SafeLoader subclass with the `!var` constructor), `expand_templates(data)`.
- `src/remote_imap_mail_rules/rules/loader.py:10`: `parse_rules` uses `yaml.load(text, Loader=RuleLoader)`, then `expand_templates`, then `model_validate`.
- `src/remote_imap_mail_rules/rules/models.py`: `RuleFile` gets `templates: dict[str, TemplateDefinition]`, plus a schema-only `TemplateInstance` (`type: template`, `defaults`, `variables`, `content: Any`) so the JSON schema accepts instances inside `when`.
  It is added to the schema via `schema.py` (post-processing `Expression`'s `anyOf`) rather than to the runtime `Expression` union, so `evaluate.py` needs no new branch.
  `content` stays `Any` in the schema, real validation happens after expansion with the rule name in the error.
- `schemas/rules.schema.json`: regenerate with `uv run python -m remote_imap_mail_rules.rules.schema --write-schema`.
- `rules/rules.example.yml`: rewrite to the valid syntax above, keep the plain unrolled rule next to the template one as the before/after.
- `CLAUDE.md`: a "Templates" bullet under Decisions and the `templates.py` entry in Layout.

## Verification

- New `tests/test_rules_templates.py`: expansion equals the hand written rule (compare `parse_rules` results), defaults and override, nested template, `!var` on a number field, missing variable, unknown variable, stray `Var`, unused template.
- `uv run pytest` including the schema `--check` test, `uv run python -m remote_imap_mail_rules.rules.schema --check`.
- Load `rules/rules.example.yml` through `load_rules`, then `demo.py --no-streamer-mode` against it if an account is configured.

## Open choice

Instantiation uses the YAML merge key `<<: *anchor` because it is the only valid way to alias and add keys.
If a shorter `use: anonaddy-forward` by name (no anchors, no merge key, `with:` for variables) is preferred, it is a small change to the expander, at the cost of leaving the `&ref`/`*ref` idea.
