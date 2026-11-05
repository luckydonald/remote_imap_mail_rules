# Process the rules from oldest first

## Context

Todo `373419c8`: when the rules run over the mails of a folder and move them, the target folder shows the mails in reverse order, because the newest mail is moved first and so gets the lowest UID there.
The existing mails of a folder are loaded newest first (`ImapClient.iter_pages` sorts the UIDs descending, `fetch_mails` returns each page descending), and the watcher and `dry_run_account` consume them in that order.
Goal: act on existing mails oldest first, as well as possible.
"Oldest" means the lowest UID, which is arrival order in the folder; sorting by `INTERNALDATE` would need an extra fetch of the whole folder and is not worth it.

## Changes

- `imap/client.py`: `iter_pages` goes ascending, oldest page first, and each page is oldest first too.
  `fetch_mails` keeps its newest-first result, because the mail browser (`list_page`) and the paged dry run depend on it, so `iter_pages` reverses each page it gets.
  Update the docstrings ("oldest first").
- `matching.py`: `load_existing` and the `matches()` docstring say "newest first per folder", change to oldest first.
  `highest_uid` is a `max`, so it is unaffected.
- `dry_run.py`: `dry_run_account` ("Run now") follows `iter_pages`, so it becomes oldest first, same as the watcher.
  `dry_run_page` (the paged preview, `before_uid` cursor, newest first) stays: the stateless cursor needs a descending walk and the preview does not write.
- `CLAUDE.md`: note under Decisions that existing mails are processed oldest first (by UID), the browser and the dry-run preview stay newest first.

## Tests

- `tests/test_imap.py::test_pages_newest_first_and_readonly`: rename to `..._oldest_first_...`, expect `[[2, 1], [4, 3], [5]]`... with the page order ascending and mails inside a page ascending, i.e. `[[1, 2], [3, 4], [5]]`.
- `tests/test_matching.py`: add a test that the `existing` matches of a folder come out with ascending UIDs.
- `tests/test_server_watcher.py` or `tests/test_actions*.py`: a move over several existing mails lands them in the target folder in the original order (FakeServer assigns UIDs ascending), if the fake supports it cheaply.

## Verification

`uv run pytest`, then the frontend is untouched so no frontend run is needed.
Note for the close step: the sync_todo MCP and the sync script were unavailable this session, so completing `373419c8` on CalDAV has to be done by the user afterwards.
