# Stage 6a: executing rule actions within an account

## Context

Stages 1 to 5 are done: rules parse, `matches()` yields `RuleMatch`, the `Watcher` logs `first_seen` and `rule_match`, and all IMAP access is read-only.
Rule `actions` (`move`, `mark_read`, `mark_unread`, `flag`, `keyword`) are parsed but nothing runs them, and the `action` log kind is reserved.
This plan adds execution of those actions inside one account, with the `action` log entries.
Cross-account moves and `user_action` entries are separate later plans (6b, 6c).

The user wants writing postponed until they trust it: with `ACTIONS_ENABLED=false` (the default) the server does not apply rules at all.
The watcher then does exactly what it does today (`first_seen` and `rule_match`) and writes no `action` events, dry or otherwise.
Instead the user gets a first-class dry run in the UI (see below) to see what a rule would do, and that stays until they are confident.

## Design

- New setting `ACTIONS_ENABLED` (default false) in `server/settings.py`, documented in `README.md` and `.example-env`.
- New module `src/remote_imap_mail_rules/actions.py`:
  - `plan_actions(match: RuleMatch) -> list[PlannedAction]` is pure, expands `rule.actions` into concrete steps (type, args).
  - `ActionExecutor` runs a plan through a short-lived write-capable `ImapClient`, never the IDLE connections of `matching.follow_folder`.
- `ImapClient` (`imap/client.py`) gets write methods: `select` (a real `SELECT`, not the forced state in `examine`), `store_flags(uid, add/remove)`, `move(uid, folder)` (`UID MOVE` when the server has the capability, else `COPY` + `STORE \Deleted` + `UID EXPUNGE`).
  Read paths stay on `EXAMINE`/`BODY.PEEK`.
- `imap/connection.py` protocol gains `select`, `expunge`/`uid_expunge`; its "only read-only commands" docstring is updated.
- Action semantics: `mark_read` adds `\Seen`, `mark_unread` removes it, `flag` toggles `\Flagged` by `value`, `keyword` toggles the keyword by `value`, `move` goes to `folder` in the mail's own account (a `move` with another `account_id` is logged as `skipped: cross_account_not_supported` until 6b).
- Loop and repeat protection:
  - Rules are processed per mail, rule by rule in file order, and the first matching rule wins: only its actions run, later rules are not looked at for that pass.
    `matches()` yields one `RuleMatch` per rule, so the Watcher groups the matches of one mail (same mail key, short batch) and takes the lowest rule index.
  - If the winning rule changed the mail, the rules are re-evaluated from the top against the updated data:
    - Flag, keyword and read-state steps are applied to the in-memory `Mail` (`dataclasses.replace` on `flags`) after the IMAP write succeeded, and the evaluator runs again on that copy, so there is no re-listing and no re-fetch (bodies already loaded stay cached).
    - A `move` ends the pass for the old mail: the mail is gone from the source folder, and the target folder's watcher sees it as `new` and starts from the top there. No extra fetch needed.
  - Termination: a rule that already ran for this mail in this pass is not applied again, there is a hard cap on rounds, and a winning rule whose steps are all `noop` (state already as wanted) changes nothing and ends the pass without moving on to later rules.
  - This also replaces the `has_event` guard for `existing` matches: actions only set state, so a rerun after a restart is a `noop` and writes no event.
  - Needs a small helper in `matching.py` (e.g. `first_match(rule_file, mail, ...)`) reusing `match_mails`/the evaluator, to be checked against how lazy body loading is wired.
  - Our own flag change comes back as a `changed` match through CONDSTORE; the rerun is a `noop` (state already as wanted), so it settles.
- Logging: the Watcher writes one `action` event per step under the source key `(account_id, folder, uidvalidity, uid)` with `detail = {type, args, status: done|noop|skipped|error, error?, new_folder?}`.
  Only written when actions are enabled (watcher) or on "Run now"; dry runs never write events.
  A move also writes an `action` event with `detail.moved_from` under the target key once the new UID is known (found by `Message-ID` search in the target), so the target mail's log does not start empty.
- Watcher (`server/watcher.py`): after logging `rule_match`, call the executor via the same single-consumer queue so order stays deterministic; errors are caught per step and logged as `status: error`, never crash the loop.
- Frontend: extend `eventLabel` in `frontend/src/model/mail-format.ts` for `action` (e.g. "Moved to Archive by rule X", "Marked read by rule X"), and update its tests.
- Docs: update `CLAUDE.md` (lines on read-only, action log, "Actions (parsed only)"), `README.md`, `ai/initial.md` (add Stage 6 with checklist and status), the `Rule.actions` description in `rules/models.py:483` (then regenerate the schema with `--write-schema`), and add `ai/plans/012_stage-6a-...md` per the earlier plan pattern.

## Dry run as a user feature

A "Dry run" button on every rule in the editor collects what the rule's actions would do, without writing anything to IMAP or to the log.

- Backend: `actions.dry_run(rule, rule_file, imap_factory, settings) -> DryRunResult`.
  Because the first matching rule wins and changes feed back into re-evaluation, it cannot look at one rule alone: it lists the existing mails of that rule's locations (existing only, no watching), runs the whole rule file's chain per mail on a virtual copy of the `Mail` (same logic as the executor, with the writes replaced by in-memory state changes), and keeps the mails whose chain involves the chosen rule.
  Each mail's result lists the whole simulated chain (which rule won in each round and its steps), so the user sees when an earlier rule shadows theirs.
  The planner and chain loop are shared with the executor through one function that takes a "writer" (real IMAP or virtual), so dry run and real run cannot drift apart.
  It also marks steps that would be no-ops (flag already set, already in the target folder) as `noop` and a move with a foreign `account_id` as `skipped`.
- API in `server/api/dry_run.py`, mounted at `/api/dry-run` behind `require_login`:
  - `POST /api/dry-run` with the rule (by name in the saved file, or the unsaved rule body from the editor so edits can be tried before saving) returns the summary: per action type (and per target folder for moves) the count of mails, plus the number of inspected and matched mails.
  - `POST /api/dry-run/details` (same body, plus optional `type` and `before_uid` paging cursor) returns the affected mails (account, folder, uid, subject, from, date) each with its list of planned steps and statuses.
  - Capped (e.g. 5000 inspected mails), with a `truncated` flag in the response.
  - Without the login/server (file-only mode) the button is hidden, like Save.
- Frontend: `DryRunPanel.vue` (a side panel / subpage on a phone, like the example mail panel) opened from a rule's "Dry run" button.
  - First a summary table ("12 × move to Archive, 30 × mark read, 3 × no-op") and counts.
  - Click a row to drill down into a paged list of the affected mails with what would happen to each; click a mail to open it in the existing mail browser (`MailMessage`).
  - Client in `dry-run-api.ts`, state kept local to the panel (Pinia not needed), route `/rules/:index/dry-run`.
- This is independent of `ACTIONS_ENABLED`: the dry run always works, since it never writes.
- "Run now" button in the same panel applies the planned steps for that rule to the mails the dry run showed:
  - `POST /api/dry-run/run` (same body) executes through the `ActionExecutor` and writes `action` events like the watcher does (same repeat protection), returns the per-step results.
  - `ACTIONS_ENABLED=false` (default) means the server does not apply rules: the endpoint answers 409 `actions_disabled`, and the button is disabled.
  - `GET /api/editor/config` gains `actions_enabled`; when false the panel shows a hint: "The server is currently not applying rules (ACTIONS_ENABLED is off). This is a dry run only."
  - Run now is only offered for a saved rule (the body must equal what the server holds), and asks for confirmation showing the summary counts.

Extra commits: `[backend] dry run` (executor-free planner, endpoints, tests with FakeServer) and `[frontend] dry run` (panel, Vitest, Playwright e2e with the API mocked).

## Safety while developing

Nothing in this stage may touch the user's live account.

- Automated tests use only the `FakeServer` and the `TEST_*` settings from `tests/settings.py`, never `.env`; the write methods are never pointed at a real host.
- `ACTIONS_ENABLED` stays unset (false) in every dev run, and `WATCH_ENABLED=false` in tests as today.
- Any manual server run uses a separate port (not 8000, not the user's running instance), its own throwaway `DATABASE_URL` and `RULES_PATH`, and only a test mailbox with `TEST_*` credentials, if one exists; otherwise only the FakeServer-backed tests and Playwright with the API mocked (port 5199) verify the work.
- No code path in tests or scripts reads `.env` or the stored production accounts.

## Critical files

- `src/remote_imap_mail_rules/imap/client.py`, `imap/connection.py`
- `src/remote_imap_mail_rules/actions.py` (new), `server/api/dry_run.py` (new), `frontend/src/components/DryRunPanel.vue` (new)
- `src/remote_imap_mail_rules/server/watcher.py`, `server/settings.py`, `server/app.py`
- `src/remote_imap_mail_rules/db/mail_events.py`
- `tests/fake_imap.py` (allow `select`, `uid store/copy/move`, `uid expunge`; keep a flag to assert nothing writes in dry run)
- `frontend/src/model/mail-format.ts`

## Commits (separate tasks, lplp style)

1. `[backend] imap`: write methods on `ImapClient` and the FakeServer, with tests.
2. `[backend] actions`: `plan_actions` and executor, tests with the FakeServer.
3. `[backend] server`: `ACTIONS_ENABLED`, watcher integration, repeat protection, event writing, tests.
4. `[frontend] mail log`: action labels and tests.
5. `[docs] stage 6a`: docs, schema regeneration, plan file.

## Verification

- `uv run pytest`: with actions disabled (default) the watcher issues no `STORE`/`COPY`/`MOVE`/`EXPUNGE`/`SELECT` and writes no `action` events; the dry-run endpoints write nothing either and "Run now" answers 409; enabled run changes the FakeServer state and logs `done`; a restart does not repeat actions; errors are logged.
- `uv run python -m remote_imap_mail_rules.rules.schema --check`.
- `cd frontend && yarn test && yarn lint && yarn build`, plus `yarn test:e2e` if the log view changed (Playwright, not Chrome tools).
- Manual: run the server against a throwaway mailbox with `ACTIONS_ENABLED=false`, check the dry-run entries in the mail log, then switch it on for one test rule only.
