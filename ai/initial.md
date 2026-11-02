This is a newly bootstrapped repo, using `base/base` to get started quickly. Here's what we'll gonna build,
please follow /commit-with-lplp-style and /code-style along the way.
Also, if not done already, please enable /plan mode for this.

To run it in the agent you may use `@ai/initial.md`.

# Initial plan

- the goal is to run mail rules via IMAP, so you can set rules independent of provider
- full rule expression syntax with groups, AND, OR, NOT
- vue js frontend
- fastapi server
- async imap
- imap push & poll support (automatic)
- support for multiple accounts
  - including moving mails between
- full action log for a mail
  - first seen
  - rule matches (= applied)
  - any actions (e.g. moves between folders, read/unread states, …)
    - either rule actions or user's own actions
- rule editor
  - classic operators
    - textual: exact, contains, startwith, endswith, …
      - toggle case sensitivity
      - regex operator, too
    - numeric/date/time: <, >, ≠, =, &gte;, &lte;, between, …
  - standard stuff, e.g.
    - account
    - folder
    - sender
    - receiver
    - subject
    - body
    - unread/read
  - useful suff others usually dont have
    - spam score headers
    - attachments
      - counts
      - type
      - size
      - …
  - easy to add queries for custom fields/headers
- rules from mail
  - (a) mail first
    - once you add a condition it fills default values from that mail
      - granularity choosable where it makes sense.
      - e.g. sender:
        - Sender Name + Email: ˋMax Mustermann <m.muster@example.com>ˋ 
        - Sender Email: ˋm.muster@example.comˋ 
        - Sender Name: ˋ Max Mustermannˋ 
  - (b) rule first
    - you get a fill from mail button on conditions.
    - otherwise similar to **(a)**

## Implementation scope

#### 1. The basic PoC
Status: to be implemented.

- There are to be understood as separate tasks for commiting.
1. YML based rules
  - pydanic
  - json schema generated from that & used
    - check ˋ../AllMyStorageˋ for that
2. no accout management
   - just load from ˋ.envˋ & document the vars in ˋREADME.mdˋ.
3. Async IMAP
  - we need to support for this stage (all read only):
    - connect to an acount
    - load INBOX asyncly & ipaginated
    - load recent changes only
    - have the server notify of updates/changes
- keep in mind we need to support all the rest at a later stage, too.
