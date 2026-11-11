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
- [x] _mail_ > _New rule from this email_: Display current chosen mail — `todo:7742c27e-221e-4553-90ab-d9cd0029f92f` _(done)_
  > - when in the rules editor, the current selected Mail should be showed as a tag/chip.
  > - basically looking similar to: `( ✉️ Title of the… | × )`
  > - the chip has a button to remove that mail, disabling all those automatic fill functionality again
- [x] in the log's last run info box, also show the next scheduled run. — `todo:81134170-a498-495e-b001-7325c8fbce4d` _(done)_
- [x] process the rules from oldest first — `todo:373419c8-c04b-4372-ab82-91652baaaccd` _(done)_
  > - at least attempt as good as possible.
  > - Reason: when moving and then displaying the folder's default sort (last changed?) it currently reverses order
- [x] cut & paste rule blocks — `todo:b0b026ed-854d-4de5-a098-067ceffb5536` _(done)_
  > - cut any block at any level
  >   - includes any sub-blocks
  >   - stores into pinia
  >   - also copies yml to real clipboard
  >     - user setting to disable
  >       - it could spam Clipboard history managers
  > - paste wherever we also can create (add) a new sub-block
  >   - paste button for that
  >   - attempts to read user (text/yml) clipboard first
  >     - user setting to disable
  >       - in case it's disabled in your browser anyways
  >       - or it spams paste request prompts you don't want to accept
- [x] fix new template not auto-filling from example mail — `todo:98e90741-4a7d-4d83-a9be-7b78680ed135` _(done)_
- [x] _Mail_ > _Rule_: add `Select as example mail` — `todo:181001a3-daac-4ee9-975a-213e5b6d4b11` _(done)_
  > - Basically _New rule from this mail_, but don't actually create any new rule.
  > - put first in drop-down list
- [x] Actual picker for _Add to existing rule …_ — `todo:a8a6cdf8-c935-4b71-b19c-898cfb094062` _(done)_
  > - currently it is a drop-down which doesn't tell you really were in the rules you are.
  > - so basically I want a view of the rules having big empty areas on any insert point which can be clicked.
  > - do that as overlay, and full screen "< back"-able on mobile
- [x] in the _Log_ view, list currently working jobs — `todo:ae83447e-1a4c-4dc0-ad2f-c8d3d3ea8b3d` _(done)_
  > - under the info box
- [x] in the mail viewer allow to see the full headers of a email — `todo:3bc42369-9781-407c-9015-eb699c8d9b56` _(done)_
- [x] Do not load the email before the folders & mails lists both are loaded. — `todo:dfab6abb-e7ad-41d5-82e9-343040e8b23d` _(done)_
- [x] add reload in folder list & email list of the email viewer — `todo:42311b99-f598-4cd1-ac36-729384bfbccd` _(done)_
  > - this includes the example viewer of the rules
- [x] unwrap button — `todo:13b0300c-4b40-46a5-8ccf-ec53d75f4fa4` _(done)_
  > - detete on an wrapping element asks if we should keep the children
- [x] Mail viewer: The dropdown menus overlap and don't close each other — `todo:e5b32090-adbc-4b99-9dd6-7b990a41ebdf` _(done)_
- [x] Adding an account is not immediately reflected in the account list. — `todo:892f49ef-c48d-4744-91c5-b28ca614ae0d` _(done)_
- [ ] fix Bigsink issues — `todo:420b2ab0-94b6-4181-a233-dd46416379cc`
  > (Create subtasks)
  - [x] Bugsink REMOTE-IMAP-MAIL-RULES-4/-5: mail browser EXAMINE of `Boxed In/Updates` fails with "nonexistent namespace (prefix INBOX.)" — `todo:6b1a79f8-187a-48e6-bdbe-576c51545427` _(done)_
    > Issues a03... : 04f/af9 (REMOTE-IMAP-MAIL-RULES-4 and -5), `/api/mail/accounts/{id}/messages` and `.../messages/{uid}`. The browser passes the folder name as given, not resolved through `ImapClient.resolve_folder`.
  - [x] Bugsink REMOTE-IMAP-MAIL-RULES-2/-7/-8: TimeoutError / "mail server did not answer in time" (watcher, /api/editor/rules, message fetch) — `todo:8377cbe7-5136-4b98-8bd0-5a517495c160` _(done)_
  - [x] Bugsink REMOTE-IMAP-MAIL-RULES-3/-6: "Task was destroyed but it is pending!" (a task is not awaited or cancelled on shutdown / rules save) — `todo:0775f42d-504f-436e-873e-870afea6b4fa` _(done)_
  - [x] Bugsink REMOTE-IMAP-MAIL-RULES-9: "login failed: NO authentication failed" on /api/mail/accounts/{id}/folders is reported as an error (expected user-config problem, should not be a Sentry event) — `todo:97650feb-165f-4eff-bf6d-71427ae7bcba` _(done)_
  - [x] Bugsink REMOTE-IMAP-MAIL-RULES-1: CancelledError on /api/editor/rules — `todo:d1caceac-5747-42e2-8e47-d4113963d02b` _(done)_
  - [x] Bugsink REMOTE-IMAP-MAIL-RULES-VUE-1: UnhandledRejection "Non-Error promise rejection captured with value: undefined" — `todo:3c2db7b4-c683-46bc-ba31-08c320ffbba3` _(done)_
  - [x] Bugsink REMOTE-IMAP-MAIL-RULES-11: TimeoutError on /api/accounts/{account_id} — `todo:ae994924-0740-483b-8c5a-2765ad3eda16` _(done)_
    > Issue c77351b4-685c-4bf5-ba0e-315ce5096428, one event, 2026-11-11T02:54Z, transaction /api/accounts/{account_id}.
- [x] optional Account check when crating & editing an account — `todo:77326de9-35af-42c6-8194-67746b52a1ad` _(done)_
- [ ] make it work offline, — `todo:28440a19-e45a-4c5c-9db5-c9367ce64dc4`
  > and cache mails until marked read.
- [ ] create MCP server to easily create, update, edit, improve rules — `todo:81f52e67-d921-4c4f-8ffd-e30fc734e066`
  > - tokens in user settings subpage
