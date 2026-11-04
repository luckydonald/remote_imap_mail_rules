**(1) `server/watcher.py`**
- `follow()` (154-201) runs `matches(..., on_inspect=lambda mail: queue.put_nowait(Seen(mail)))` (183). Each yielded `RuleMatch` is queued (184). A single `record()` task (203-227) drains the queue in order and commits per entry. Entries are `Seen | RuleMatch | Act` (44).
- `write()` (270-286):
  - `Seen` writes `first_seen` once, guarded by `has_event`.
  - `RuleMatch` writes `rule_match` with `detail={"match_kind": kind}`. `existing` is deduplicated per rule; `new` and `changed` are always written.
  - `add()` (288-299) wraps `mail_events.record_event` with the mail's key and `message_id_of(mail)` (50, from the Message-ID header).
- Actions: `Act` (37) is queued once per mail via the `pending` set. `record()` calls `runner.run(mail)`, then `write_actions` (229-248) writes one `action` event per step with status done, error or skipped (`LOGGED_STATUSES`, 46). The detail is `{type, status, **args, reason?}`. After a move, `continue_log` (250-268) writes `moved_in` under the new key.
- Own-action tracking: there is none beyond the log itself. `allow_move` (141-152) counts past `action` events with type `move` and status `done` for the same Message-ID. Nothing records which flag changes or UIDs the runner just made, so a watcher-detected flag change caused by our own `store_flags` cannot be told apart from a user's. You would need a suppression set or a time window.
- A `changed` mail carries only its new state:
  - `Mail` (`mail.py:42-`) has `flags` (frozenset), `modseq`, `uidvalidity` and headers. There is no old-flags field.
  - `RuleMatch` is yielded only if a rule matches, so non-matching changed mails never reach the watcher.
  - `on_inspect` does fire for changed mails, since `match_mails` calls it for every mail. But `Seen` is handled only for `first_seen`, and it does not say whether the mail was existing, new or changed.

**(2) `matching.py` and `imap/watcher.py`**
- `imap/watcher.py:56` `watch()` yields only hint `ChangeEvent`s (push or poll), with no diff.
- `matching.py:102-136` `follow_changes` compares `uidvalidity` and `highestmodseq` from `poll_state`:
  - On a UIDVALIDITY change it reloads everything as `existing` (112-117).
  - New mails come from UIDNEXT (119-126, `fetch_new`).
  - Flag changes come from `fetch_changed(since modseq)` (127-133, `client.py:359`, `FETCH ... CHANGEDSINCE`). The result is filtered to `uid <= known_uid` and matched as `MatchKind.changed`. This needs CONDSTORE; without it `fetch_changed` returns `[]`.
- Not exposed anywhere:
  - No flag diff, because no previous flags are kept.
  - No deletes or vanished mails. There is no `VANISHED` or EXPUNGE handling, and no UID-set comparison.
  - No non-matching changed mails reach the consumer (see `match_mails`, 63-76).
- Implementation implication: a new hook is needed in `follow_changes`, e.g. `on_change(old_flags, mail)` or a new `ChangedMail` item. It would need a per-folder `dict[uid, flags]` snapshot, seeded in `load_existing`. For deletes or moves, diff the folder's UID list via `SEARCH ALL` on each poll, or use QRESYNC/VANISHED.
- To tell our own actions from the user's, compare against recorded `action` events or a runner-side expected-state set.

**(3) Event storage, API and frontend**
- `db/models/mail_event.py:15-22`: `EventKind` is `first_seen | rule_match | action | user_action`. The docstring says "`user_action` is reserved: nothing writes it yet".
- `MailEvent` (25-): `id, account_id, folder, uidvalidity, uid, message_id, kind` (String(32)), `rule_name, detail` (JSON, default `{}`), `created_at`. The index is `(account_id, folder, uid)`.
- `db/mail_events.py`: `record_event` (12), `list_events` (40, oldest first), `list_events_by_message_id` (51, optional kind), `has_event` (61).
- `server/api/events.py:32`: `GET /accounts/{id}/messages/{uid}/events?folder=` returns `EventOut{id, kind, rule_name, detail, created_at}`. It is kind-agnostic, so no API change is needed.
- Frontend:
  - `frontend/src/model/mail-format.ts:75-88` `eventLabel` already has `case 'user_action': return 'Changed by you'`, a generic placeholder that ignores `detail`.
  - `frontend/src/components/MailLog.vue` renders `<li :class="event.kind">` with time and label. It needs no change except richer labels.
  - `action` labels use `describeLoggedAction(event.detail)`; see `__tests__/dry-run.spec.ts:64-80` for the label tests.
  - The `detail` shape for `user_action` is free to define. For example `{type: "flags", added: [...], removed: [...]}`, `{type: "deleted"}` or `{type: "moved", to: ...}`, mirroring the action detail's `type` convention.

**(4) Tests**
- `tests/test_server_watcher.py`:
  - Setup helpers: `StaticRules` (34), `factory` fixture (57, sqlite), `make_watcher` (71), `kinds` (76, a list of `(kind, rule_name)`), `until` (83), `_has` (121), `action_events` (249), `make_acting_watcher` (244), `action_server` (235, caps `IMAP4REV1, IDLE, CONDSTORE, MOVE`).
  - Tests: `test_logs_first_seen_and_rule_matches` (92), `test_restart_does_not_log_existing_mails_twice` (126), `test_without_rules_or_when_disabled_nothing_happens` (139), `test_connection_failures_are_retried` (155), `test_account_and_rule_edits_restart_the_watcher` (179), `test_actions_are_applied_and_logged_when_enabled` (257), `test_nothing_is_written_when_actions_are_disabled` (279), `test_a_restart_does_not_repeat_actions` (295), `test_a_move_to_another_account_continues_the_log_under_the_new_key` (331), `test_a_mail_that_was_moved_too_often_is_not_moved_again` (371).
  - Pattern: `server = FakeServer(); server.add("INBOX", 1, "invoice one"); watcher.start(); await until(...); await asyncio.sleep(0.1); server.add(...) / server.set_flags(folder, uid, "\\Seen"); server.push()`.
- `tests/fake_imap.py`: `FakeServer` (44) has `add` (53), `set_flags` (63) and `push` (73). There is no delete or expunge helper, so one would need adding for the vanished-mail case.
- `tests/test_matching.py`: `test_new_and_changed_mails_arrive_after_existing` (64), `test_new_mail_is_not_reported_again_as_changed` (87), `test_uidvalidity_change_reloads_folder` (118).
- `tests/test_db_mail_events.py`: `test_record_and_list_oldest_first` (39), `test_has_event_distinguishes_rule_and_uidvalidity` (53), `test_events_vanish_with_their_account` (65).
- `tests/test_server_events.py`: `test_lists_the_log_of_one_mail_oldest_first` (48), `test_empty_for_a_mail_without_log` (62).

**(5) Frontend condition editor and header picker**
- `frontend/src/components/ConditionNode.vue`:
  - `header` is one of `expressionTypes` (`model/catalog.ts:35-47`, label "Header" at 56).
  - Lines 103-106 route `text`, `address` and `header` to the same component, `condition/TextLikeEditor.vue`, imported there as `AddressEditor`.
  - `fillable` (33) includes `header`, and the "From mail" button calls `fillExpression`.
- `TextLikeEditor.vue:44-46`: for `header`, the name is a plain free-text `<input v-model="model.name" placeholder="Header name">` wrapped in `FieldValue` (template-variable aware; `components/FieldValue.vue`, 36 lines). `text` and `address` use a `<select>` over `textFields` and `addressFields`.
- `catalog.ts:94-95`: `newExpression('header')` returns `{type, name: 'X-Header', operator: 'contains', value: ''}`. `HeaderCondition` is in `model/types.ts:35-42`. The enums come from the JSON schema, with `enumOf('TextField')` and similar at 15-24.
- Picker plan:
  - Replace the header-name input at `TextLikeEditor.vue:45` with an input plus `<datalist>` of common headers. Add a new `commonHeaders` list to `catalog.ts`, since there is no existing list. Candidates: `List-Id`, `X-Spam-Flag`, `X-Mailer`, `Authentication-Results`, and so on.
  - Add the header names of the currently open mail from `useMailStore().context`. `fill-from-mail.ts:46` `headerValues(detail, name)` shows that `detail.headers: Header[]` (`mail-api.ts:46-59`) has `name` and `value`.
  - `components.spec.ts`, `catalog.spec.ts` and `fill-from-mail.spec.ts` are the likely frontend test homes.