# Plan: `demo --verbose` and `--streamer-mode`

## Context

`python -m remote_imap_mail_rules.demo` only prints mails that match a rule, so there is no way to see which mails were looked at.
`--verbose` should list every inspected mail (account, folder, mail id, title).
Because agent runs must not see real subjects or addresses, `--streamer-mode` masks them, and non-interactive runs must choose explicitly.

## Changes

### `src/remote_imap_mail_rules/matching.py`

- Add `InspectCallback = Callable[[Mail], None]` and an optional `on_inspect: InspectCallback | None = None` parameter to `matches()`.
- Thread it through `follow_folder` → `load_existing` / `follow_changes` → `match_mails`, where it is called once per mail before the rule loop (so mails are reported even when no rule matches, and once per mail rather than once per rule).
- Default `None` keeps the existing API and tests unchanged.
- A callback is chosen over logging because the demo needs the `Mail` object itself and the masking must happen in the demo, not in the library.

### `src/remote_imap_mail_rules/demo.py`

- Parse args with `argparse`: `--verbose`, and `--streamer-mode` / `--no-streamer-mode` via `argparse.BooleanOptionalAction` (default `None`).
- Non-interactive detection: `not (sys.stdin.isatty() and sys.stdout.isatty())`.
  If it is non-interactive and the streamer flag is `None`, call `parser.error("... requires --streamer-mode or --no-streamer-mode")` (exit code 2).
  Interactive and unset means streamer mode off.
- Verbose line, printed from `on_inspect`: `[inspect] account=<name or id> folder=<folder> uid=<uid> title=<subject>`.
  "Mail uuid" is the IMAP `uid`, which is what `Mail` carries (there is no real UUID; it is only unique per folder, so folder is printed next to it).
- Streamer mode applies to every printed mail, including the existing match line, which currently prints `From` and `Subject`:
  - `mask_title(title)` → `hashlib.md5(title.encode()).hexdigest()`.
  - `mask_email(addr)` → first + `…` + last char of the local part, `@`, first + `…` + last char of the domain without its TLD, then the TLD kept: `mike@example.com` → `m…e@e…e.com`.
    Local parts or domain names of length 1 stay as-is (`a…a` would be misleading); multi-label domains mask everything before the last label.
  - `From` header: extract addresses with `email.utils.getaddresses`, print only the masked addresses and drop display names, since names leak identity too.
- Pass `on_inspect` only when `--verbose` is set.
- Keep the existing `main()` structure and `# end` comment style per `/code-style`; the masking helpers are small pure functions at module level so they can be tested.

### Tests

- New `tests/test_demo.py`: `mask_email` (normal, short parts, multi-label domain), `mask_title` (md5 value), argument handling (non-interactive without a flag exits with 2, with either flag passes).
- `tests/test_matching.py`: with a fake IMAP connection from `tests/fake_imap.py`, `on_inspect` is called for non-matching mails too, once per mail.

### Docs

- `CLAUDE.md` Layout line for `demo.py`: mention `--verbose`, `--streamer-mode` / `--no-streamer-mode` and that agents must pass one of the latter two.

## Verification

- `uv run pytest`.
- `uv run python -m remote_imap_mail_rules.demo --verbose --streamer-mode` shows hashed titles and masked addresses.
- `uv run python -m remote_imap_mail_rules.demo --verbose < /dev/null` (non-interactive) fails with the usage error, and passes with `--no-streamer-mode`.
