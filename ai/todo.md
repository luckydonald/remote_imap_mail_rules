# Todos

## For Agents
If you are an agent tasked to process/fix this file:

- Fix the outstanding issues (unchecked items) below.
- At least 1 commit (/commit-with-lplp-style) per task, possibly more where it makes sense.
- You are allowed to plan for one or more items as it makes sense.


## How to sync from CalDAV

Source: `sync_todo` MCP, calendar `TODO: Today` (`calendar_id` 7). Each item ends with its todo `uid`, and may optionally include a body as blockquote the next lines.

To complete one:
1. tick the box - good to squash into the code commit
2. call `mcp__sync_todo__complete_todo(calendar_id=7, uid=<uid>)`.
3. Finally call `../DockerTgBot/scripts/sync_todos.py --project base` to update this file, which may add new tasks.
   - Generally, leaving out the project parameter is fine, too, as this syncs all projects, which is what you want to do eventually anyway.
   - If you specify the project you may also occasionally add flags to reduce the length, which may be good if you got more than 20 todos completed.
     - Add `--purge-missing` if you want to remove items not tracked in the todo list. Still incompleted ones should be duplicated to the `sync_todo` MCP first.
     - Add `--purge-complete` to clean up completed tasks.

## Todos synced from CalDAV

- [x] allow `/code-style` and suffix like `/code-style .md .py` or `/code-style md` in the query-autocommit hook to not be displayed — `todo:2eaeb8ce-67be-4878-a8df-3fb3311a4be8` _(done)_
  > • there's an array to fill
- [x] add `mcp__sync_todo__list_calendars` to allowed calls in [`ai/settings/settings.json`](./settings/settings.json). — `todo:87dac3b4-331e-4043-8f5b-cc5e45c113ab` _(done)_
- [x] add memory that if we stumble over preexisting errors in unittests or typing, those should be fixed as a separate commit automatically, too. No need to explicitly seach for those though. — `todo:8ae825eb-3ef2-4d84-8180-a937d7e2bb3c` _(done)_
- [x] Write memory to NEVER EVER run file searches from `/`. — `todo:d23bc543-c583-4dc1-a8ed-1141c92f6822` _(done)_
  > Also disallow `find / …` via [`ai/settings/settings.json`](./settings/settings.json).
- [x] _mail_ > _add to existing rule_ is behind mail list panel. — `todo:a62dffd2-029e-49b5-a8e6-70826db93104` _(done)_
  > Probably a z-index issue.
- [x] _mail_ > _add to existing rule_: Support Address type — `todo:2837fb45-8a22-4c00-bd1e-25a4a65e2be4` _(done)_
  > - the `address` type generally needs to be prefilled when an email is selected as template to fill from.
  >   - so if i select _Address field_ > _`from`_ > _`full`_ / _`name`_ / _`address`_ / _`local_part`_ / _`domain`_, it should fill those, too.
- [x] _mail_ > _add to existing rule_: Support templates, too. — `todo:587d8daf-9367-4538-add7-e2a3c1052e36` _(done)_
  > - Based on the fields, the variables go into, we can make assumptions about which field we need to place there, and hence can fill it in.
  > - The example file under version control in `rules/` has such template.
  >   - for that the `address` type generally needs fill, which should be completed by a prior todo task.
- [ ] _mail_ > _New rule from this email_: Display current chosen mail — `todo:7742c27e-221e-4553-90ab-d9cd0029f92f`
  > - when in the rules editor, the current selected Mail should be showed as a tag/chip.
  > - basically looking similar to: `( ✉️ Title of the… | × )`
  > - the chip has a button to remove that mail, disabling all those automatic fill functionality again
