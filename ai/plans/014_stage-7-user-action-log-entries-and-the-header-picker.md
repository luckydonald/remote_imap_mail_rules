# Stage 7: `user_action` log entries and the header picker

**Commit style:** Skill `/commit-with-lplp-style` is active — auto-commit following it for this implementation.

## Context

`ai/initial.md` lists two open items, both under "Not built yet".
First, `user_action` entries of the mail log: the user's own changes (read/unread, flagged, moved, deleted in another mail client) next to the rule actions.
Second, an easy picker for custom headers in the editor.
The table kind `user_action` and the frontend label (`eventLabel` in `frontend/src/model/mail-format.ts:75`) already exist, nothing writes it yet.

## Part A: detect and log user actions

Detection runs in the server `Watcher` per folder, with a snapshot of `uid -> flags` kept in memory, seeded when the folder is first loaded.
A change that is not ours is a user action.

Core changes:

- `matching.py`: `follow_changes` (102-136) gets a new optional hook `on_change(ChangeEvent)` next to `on_inspect`.
  - Flag change: for every mail returned by `fetch_changed` (also the ones no rule matches), call it with `old_flags` (from the snapshot) and the new `Mail`, then update the snapshot.
  - Vanished mail: after each poll, when `UIDNEXT` / `MODSEQ` moved, run a `UID SEARCH ALL` (new `ImapClient.list_uids`) and diff against the snapshot keys.
    Report each missing UID as `gone`; a UIDVALIDITY reload resets the snapshot without reporting.
- `server/watcher.py`: new queue entry `UserChange` handled in `write()` (270-286).
  - Flags: one `user_action` event with `detail {type: "flags", added: [...], removed: [...]}`, system flags without backslash noise kept as sent (`\Seen`).
  - Gone: `detail {type: "gone"}`; we cannot know whether it was moved or deleted, and the label says "Left the folder".
    If a `moved_in` or `first_seen` for the same `message_id` appears in another folder later, the existing `message_id` link already shows it, no extra logic.
- Own actions are not user actions.
  - After `write_actions` (229-248) records a `done` step, the watcher applies the step's result to the snapshot (flag add/remove for `mark_*`, `flag`, `keyword`; drop the UID for a `move`), so the next diff finds nothing.
  - Reuse `Watcher.allow_move` bookkeeping style; no time windows.
  - Race: our `store_flags` can land before the snapshot update.
    The snapshot is updated under the same per-folder lock `record()` already serializes on (203-227), and the hook only queues entries, so ordering is by the queue.
- `db/models/mail_event.py:15`: fix the docstring ("reserved" goes away). No migration, `kind` is a plain string.
- Not logged when `WATCH_ENABLED=false`.
  The first load never writes `user_action` (existing mails are the baseline).

Frontend:

- `eventLabel` for `user_action`: "You marked it read", "You flagged it", "You removed the keyword X", "Left the folder" from `detail`, falling back to the current "Changed by you".
  Mirror `describeLoggedAction` and add cases next to `__tests__/dry-run.spec.ts:64-80` style tests.
- `MailLog.vue` needs no structural change.

Tests (Python, `tests/test_server_watcher.py` pattern with `FakeServer`):

- Add `FakeServer.delete(folder, uid)` in `tests/fake_imap.py` and make `list_uids` work against it.
- A user flag change after start logs a `user_action` `flags` event; the same change made by a rule action logs only the `action` event.
- A deleted mail logs `gone`; a mail moved by a rule logs `action` + `moved_in` and no `gone`.
- A restart does not log anything for the initial state.
- `test_matching.py`: `on_change` receives the old flags and the vanished UIDs.

## Part B: header name picker

- `frontend/src/model/catalog.ts`: new `commonHeaders` list (`List-Id`, `X-Mailer`, `X-Spam-Flag`, `Authentication-Results`, `X-Priority`, `Received`, `X-Original-To`, ...).
- `frontend/src/components/condition/TextLikeEditor.vue:45`: keep the free-text input (inside `FieldValue`), add a `<datalist>` with `commonHeaders` plus the header names of the open mail from `useMailStore().context` (`detail.headers`, de-duplicated, mail's own first).
- Tests in `src/__tests__/catalog.spec.ts` and `components.spec.ts`; one Playwright case: open the example mail, add a header condition, the datalist offers that mail's headers.

## Docs

- `ai/initial.md`: new stage 7 section with a checklist, "Not built yet" shrinks to nothing.
- `CLAUDE.md`: Decisions get a "User actions" paragraph (snapshot diff, own actions applied to the snapshot, `gone` meaning) and the `user_action` mention in "Action log" changes from reserved to written.
- `README.md` if it lists the log kinds.

## Commits (separate tasks)

1. `[backend] imap|matching`: `list_uids`, `on_change` hook, tests.
2. `[backend] action log`: `Watcher` writes `user_action`, own-action suppression, tests.
3. `[frontend] mail log`: labels and tests.
4. `[frontend] editor`: header picker and tests.
5. `[docs]`: `ai/initial.md`, `CLAUDE.md`.

## Verification

- `uv run pytest` (new tests above, schema and migration drift tests unchanged).
- `cd frontend && yarn test && yarn lint && yarn build && yarn test:e2e`.
- Only `FakeServer` and `TEST_*` settings; never the live account, no Chrome tools (Playwright for the frontend).
