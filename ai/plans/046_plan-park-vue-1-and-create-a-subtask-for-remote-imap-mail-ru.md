# Plan: Park VUE-1 and create a subtask for REMOTE-IMAP-MAIL-RULES-11

## Context

The todo loop took VUE-1 (`3c2db7b4`, "Non-Error promise rejection captured with value: undefined").
Both Bugsink events have no stack trace and fired while the page was idle, and the code has no source for a rejection with `undefined`.
You decided to skip that todo until there are new events, so nothing is changed for it.

Bugsink also has REMOTE-IMAP-MAIL-RULES-10 and -11 without a todo.
-10 ("Task was destroyed but it is pending!" on `/api/accounts/{id}`) is believed fixed by the recent backend commits, so it gets no todo.
-11 (`TimeoutError` on `/api/accounts/{id}`, one event, 2026-11-11) gets one.

## Steps

1. `create_todo` in calendar 7 with `parent_uid` `420b2ab0-94b6-4181-a233-dd46416379cc` and the `mailRules` tag, titled "Bugsink REMOTE-IMAP-MAIL-RULES-11: TimeoutError on /api/accounts/{account_id}".
2. Run `uv run scripts/°base/ai/todos/sync_todos.py --project remote_imap_mail_rules` and fold its `[TODOs]` commit per the lplp style if it is not pushed yet.
3. Stop. No code changes, no VUE-1 work.

## Verification

`ai/todo.md` shows the new subtask under "fix Bigsink issues" and VUE-1 is still open.
