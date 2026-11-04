Note: a `YamlPanel.vue` already exists and does most of a raw mode (view `{kind:'yaml'}`), but it shows the generated YAML, not the server's raw text.

**1. Frontend** (`/Users/user/Documents/programming/Python/remote_imap_mail_rules/frontend/src/`)

- `components/AppShell.vue`
  - Topbar buttons are at lines 223-264. They are hidden on the mail screen.
  - Open… is line 224, with a hidden file input at 225, `onPick` at 131 and `openFile` at 122.
  - New is line 226 and calls `reset()` (168), which loads `rules: []`. Undo and Redo are at 227-244, and `onKey` (173) handles Ctrl/Cmd+Z.
  - Copy YAML is line 245 (`copy()` at 159). It copies `store.yaml.value` and shows a notice.
  - Download is line 246 (`download()` at 150). It uses a Blob with `fileName`.
  - Save is lines 247-256, shown only when `serverFile !== null`. It is disabled when `saving || !dirty || problems.length > 0`. `save()` (105) calls `saveRules(store.yaml.value)`, then `store.markSaved(undefined, text)`.
  - Errors from `save()` go to `notice`, as `Not saved: <messages joined by "; ">`.
  - The badge at 257-263 shows "N problems" (a click switches to the yaml view) or "valid".
  - Drag and drop is the `@drop` handler on the `.app` div (190), through `onDrop` (138). It opens a dropped file.
  - `connect()` (63) calls `fetchConfig` then `fetchRules`. It runs `store.load(text, label)` and then `store.markSaved(label)`, and sets the notice.
  - `notice` is a clickable `<p class="notice">` at line 266. The YAML view is the default `<YamlPanel v-else />` at line 282.
- `model/store.ts`
  - `View` (line 8) includes `{kind:'yaml'}`.
  - `load(text, name?)` (90) calls `parseRulesWithComments`. It sets `comments`, the file fields and `fileName`, resets `serverFile = null`, and picks the view. It throws `RulesParseError` on bad YAML.
  - `load()` does not call `markSaved`, so loading from the YAML panel on a server file sets `serverFile` to null. Save then disappears, and `connect()` has to call `markSaved(label)` itself. Raw mode must work around this by calling `markSaved(name, savedText)` after `load`, or by adding a separate apply function that keeps `serverFile`.
  - Undo and redo (48-87) use JSON snapshots of the file, limited to 100 (`HISTORY_LIMIT`, line 10). The watcher runs with `flush: 'sync'`, and `restore` sets `applying`. Comments are not part of the snapshots.
  - `yaml` is computed as `stringifyRules(file, comments)` (103). `dirty` is `serverFile !== null && yaml !== savedYaml` (104). `markSaved(name = serverFile, text = yaml)` is at 107. `problems` is `validateRules(file)` (102).
- `model/yaml-io.ts`
  - `parseRulesWithComments` (61) uses `parseDocument` with `merge:false` and the `!var` custom tag.
  - Parse errors become `RulesParseError`, with `doc.errors` messages joined by newlines (63-64). A non-mapping top level gives another `RulesParseError` (67).
  - `<<: *anchor` merges become `{type:'template', ref, variables}` (`replaceUses`, 35). Comments are collected via `collectComments(doc)`.
  - `stringifyRules` (82) rebuilds the doc, re-applies comments and regenerates anchors named `template-<name>` (78). It turns `{var:x}` into `!var x`, adds the `# yaml-language-server: $schema=` header, and uses `lineWidth: 0`.
  - Because it regenerates, raw text that is not normalised changes on the first edit. Anchors, formatting, and comments on entries that no longer exist are lost.
  - `expandRules` is at 146.
- `model/validate.ts`
  - `Problem` is `{path, message, rule, template}` (8). `validateRules` (65) runs Ajv2020 against `@schema`, using `expandRules` first. It skips anyOf, oneOf and if errors and de-duplicates. `checkUse` (85) adds the missing-template and variable messages.
  - Messages are Ajv text, for example "must have required property: x", with the path as `instancePath`.
- `model/api.ts`
  - `fetchConfig` (24) returns the config, `'login'` for 401 or 503, or null.
  - `fetchRules` (39) returns text or null on 404. `saveRules` (47) does a PUT with `Content-Type: text/plain; charset=utf-8` and the raw body.
  - On failure `saveRules` throws `SaveError.messages`: `detail` as an array of strings, a string, or `The server answered N.`.
  - `EditorConfig` (5) has `source: 'file'|'database'`, `file_name`, `exists` and `actions_enabled`.
- Problem display: `components/YamlPanel.vue`, lines 33-53, is a `ul.problems` with links to a rule or the templates view plus `<code>path</code> message`. `RuleEditor.vue:17` and `RuleList.vue:7,29,79` show per-rule counts.
- `YamlPanel.vue`
  - It has a textarea `draft` (55, aria-label "YAML"), Apply (57) and Reset (58). It resyncs `draft` from `store.yaml` on every change (11).
  - Apply calls `store.load(draft)` and shows `.message.error` (54) on failure.
  - Its hint (29-32) says to paste a rules file and apply it, and that comments are kept.
  - Gaps for raw mode: the panel never shows or sends the server's raw text. It uses the regenerated YAML and drops `serverFile`. It also has no Save button and no server-side error display.

**2. Backend** (`/Users/user/Documents/programming/Python/remote_imap_mail_rules/src/remote_imap_mail_rules/server/`)

- `api/editor.py`
  - `GET /rules` (35) returns a `text/plain; charset=utf-8` body, or 404 with `"There are no rules yet."`.
  - `PUT /rules` (45) returns 204. The body is the raw YAML (`request.body()`, any content type).
  - Bad UTF-8 gives 422 with `detail=["The body is not valid UTF-8."]`. Invalid rules give 422 with `detail=e.messages`, a list of strings.
  - After a successful PUT it restarts the watcher and runs git auto as background tasks. `GET /config` is at 28.
- `rules_file.py`
  - `InvalidRules.messages` is at 14.
  - `validate` (24) uses `parse_rules`. It reports `YAML: <err>` for YAML errors, and `loc.path: msg` per pydantic error, with `(root)` for the root.
  - `write_atomic` is at 35, and `save_text` at 64 validates then writes atomically.
  - Messages carry no line numbers except whatever the PyYAML error includes.
- `rules_store.py`
  - `FileRulesStore` (38-57): `read_text` returns the file bytes as-is, and `save_text` validates and writes the text verbatim. Comments, anchors and formatting are preserved exactly.
  - `DatabaseRulesStore` (60-103): `read_text` (81) returns `rule_rows.to_yaml(load_rule_file)` (`db/rules.py:95`), a freshly dumped YAML. It has no original comments, formatting or header.
  - `save_text` (88) validates, then runs `append_comments(text, parse_rule_file(text))` (`rules/comments.py:79`). That appends each rule's comments to its `description`, one line each and de-duplicated, as a `|` block. Only comments attached to rules survive, and they come back as `description: |` text. It then calls `replace_rule_file` and `write_mirror`, which writes `rules.yml` to the git mirror dir.
  - So in database mode a PUT does not keep comments as comments. Templates and anchors survive through the non-concrete form.

**3. Tests to mirror**

- Backend:
  - `tests/test_server.py`: `test_get_existing_file` (59), `test_put_valid_writes_file_with_comments` (68), and `test_put_invalid_is_422_and_keeps_file` (77, parametrised with `INVALID_SCHEMA` and `INVALID_YAML`).
  - `tests/test_server_rules_db.py`: `test_empty_database` (69), `test_save_and_read_back` (75), `test_templates_survive_the_round_trip` (83), `test_invalid_is_422_and_changes_nothing` (94) and `test_comments_end_up_in_the_description` (140).
  - Others in that directory are `test_server_watcher.py` and `test_server_git.py`. I did not find a test file named `test_server_editor*`.
- Frontend unit tests (vitest):
  - `__tests__/api.spec.ts` covers `fetchRules`, `saveRules` and `SaveError` (lines 27-52).
  - `store.spec.ts` has `store server state` (31-46) for dirty, `markSaved` and leaving server mode.
  - `yaml-io.spec.ts` covers parse and serialize.
  - `components.spec.ts` has an `AppShell` describe (76-100) that mounts the shell and checks valid or problems.
- Frontend e2e (playwright):
  - `e2e/server.spec.ts` has a `mockServer(page, rejectWith?)` helper (lines 19-34). It routes `**/api/editor/config` and `**/api/editor/rules`, records `puts`, and can reject with a 422 `{detail:[...]}`.
  - Tests at lines 36, 52 (shows what the server rejected) and 60 (no server).
  - `e2e/editor.spec.ts` has a YAML-view test at 111 ("applies YAML typed into the YAML view", using `getByLabel('YAML')` and the Apply button). The broken-YAML test is at 123, and the download, comments and copy tests are at 129, 142 and 155.