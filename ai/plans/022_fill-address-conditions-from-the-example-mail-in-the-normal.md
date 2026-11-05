# Fill address conditions from the example mail in the normal rule editor

## Context

Todo `2837fb45-8a22-4c00-bd1e-25a4a65e2be4` (project remote_imap_mail_rules, `ai/todo.md`): "_mail_ > _add to existing rule_: Support Address type".
The user clarified that the gap is in the normal rule editor, not in the "Add to a rule" dialog, which already has the part select and works.
With an example mail open, an `address` condition does not take its value from the mail unless the user presses "From mail" by hand.
Two paths leave the value empty:

- Changing a condition's type to `address` in `ConditionNode.changeType` uses plain `newExpression(type)`, so the value stays `''`.
- Changing an address condition's `field` (`from` to `to`) or `part` (`address` to `domain`) in `TextLikeEditor.vue` keeps the old value, so it no longer matches the mail.

The intended outcome: with a mail selected, the address condition starts filled and follows the field and part the user picks.
This is the prior task of `587d8daf` (templates), which needs the address fill.

## Changes

All in `frontend/src`.

1. `model/fill-from-mail.ts`:
   - New `shouldRefill(node, previous, ctx)`: true when the value is empty (`''` or `[]`), or equals what the mail gave for the previous field and part.
     This way a value the user typed is never overwritten.
   - New `refillAddress(node, ctx)`: `fillExpression(node, ctx, node.part)` (the part is already stored in the node, `part` defaults to `address`).
2. `components/ConditionNode.vue` `changeType`: after `newExpression(type, ...)`, if `mail.context` is set and the type is `address` (and `text`, `header`, `number`, `date`, `bool`, which `fillExpression` handles the same way), pass it through `fillExpression` with part `address`.
   Group, `presence` and `template` types stay untouched (`fillExpression` returns them as is).
3. `components/condition/TextLikeEditor.vue`: `watch` on `[model.field, model.part]` for `address` nodes.
   When `mail.context` exists and `shouldRefill` holds for the previous field and part, replace the value with `refillAddress`.
   The `in` operator gets all values, as `fillExpression` already does.
   Field and part `Var`s (template variables) are skipped, `fillExpression` already returns those unchanged.
4. Undo: the refill happens in the same edit as the field change, so one undo step takes both back (check against `store.ts` history batching, fall back to the watch running in the same tick).

## Tests

- `src/__tests__/fill-from-mail.spec.ts`: `shouldRefill` (empty, auto-filled, user-typed, `in` list) and `refillAddress` for each part, plus a mail without a name (part `name` leaves the node alone).
- `e2e/fill-from-mail.spec.ts` (mocked server, as the existing cases): with a mail open, (a) change a condition's type to Address and the value is the sender's email, (b) switch part to `name` and the value follows, (c) type a custom value, switch part, and the value is kept.

## Docs

Add one sentence to the "Fill from mail" bullet of `CLAUDE.md`: a type change to a fillable type and a field or part change of an address condition refill from the open mail unless the value was typed by hand.

## Verification

`cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e` (Chromium and `webkit-ipad`), then `uv run pytest` once as the repo-wide check.
Playwright only for the UI, no live account, per the project memory.

## Close-out (todo-loop)

Plain commits with `/commit-with-lplp-style`, tick the box in `ai/todo.md`, `complete_todo(7, 2837fb45-…)`, then `sync_todos.py --project remote_imap_mail_rules`.
The `sync_todo` MCP failed to connect in this session (`CONNECTION_CLOSED`), so completing on CalDAV needs the user to retry the MCP, or I report it as left over.
Tag the prior HEAD with `scripts/tag_backup.py`, rebase into one work commit and check `git diff <bak-tag> HEAD` is empty.
The step-1 sync was skipped in plan mode (it commits), so run it first thing after approval.
