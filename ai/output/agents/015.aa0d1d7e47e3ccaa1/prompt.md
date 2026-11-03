Medium thoroughness, read-only. In /Users/user/Documents/programming/Python/remote_imap_mail_rules explore what stage 5 (a read-only mail browser for accounts registered in the server) can build on. Report concisely with file:line refs:
1. src/remote_imap_mail_rules/imap/: ImapClient API (client.py), connection.py, fetch.py, bodystructure.py. What is available for listing folders, paginated header fetch, fetching a full body/part/attachment? What is missing for a mail viewer (folder list with attributes, message body rendering, attachments download, search)?
2. src/remote_imap_mail_rules/server/: app.py, settings.py, api/accounts.py and api/editor.py patterns (routers, dependencies, DB session, error handling, how tests use TestClient), and any existing auth.
3. src/remote_imap_mail_rules/db/accounts.py: how account credentials are decrypted and turned into IMAP settings.
4. Existing tests layout for the server and imap (fakes).
Do not write files.