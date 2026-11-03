# Writing rules

A rules file is a YAML file (path in `RULES_PATH`, see `example.yml`) that says *which mails* to look at and *what to do* with them.
Your editor can check and complete it if the first line points at the generated schema:

```yaml
# yaml-language-server: $schema=../schemas/rules.schema.json
rules:
  - name: ...
```

Every rule has the same four parts:

```yaml
rules:
  - name: Unread invoices          # shown in the output, any text
    enabled: true                  # optional, false switches the rule off without deleting it
    locations:                     # WHERE to look
      - account_id: 6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11
    when:                          # WHICH mails match
      type: text
      field: subject
      operator: contains
      value: invoice
    actions:                       # WHAT to do (optional)
      - type: mark_read
```

Currently the program finds and prints the matching mails.
The `actions` are checked for typos but not carried out yet.

## Where to look: `locations`

A rule lists one or more places.
Each place is an account, a folder and optionally the folders below it.

| Key | Default | Meaning |
|---|---|---|
| `account_id` | required | The `IMAP_ACCOUNT_ID` of the account (a UUID). It is an id, not the display name, because names can change. |
| `folder` | `INBOX` | The folder to watch. |
| `recursive` | `false` | `true` also covers every folder below this one. |

Because a rule can have several locations you never need to copy a rule just to apply it to two inboxes:

```yaml
rules:
  - name: Invoices from both accounts
    locations:
      - account_id: 6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11
      - account_id: 0b8d3f4c-2b6e-4f0e-8f4a-3c8f6f1e9d22
      - account_id: 0b8d3f4c-2b6e-4f0e-8f4a-3c8f6f1e9d22
        folder: Mailing lists
        recursive: true
    when:
      type: text
      field: subject
      operator: contains
      value: invoice
```

A folder that does not exist is skipped with a warning.
The rule's own `account_id` and `folder` can also be tested inside `when`, see the fields below.

## Which mails: `when`

`when` is one single condition, or a group that combines several.
Every condition has a `type`, which tells what kind of thing it checks.

### Combining conditions: AND, OR, NOT

| `type` | Means | Contains |
|---|---|---|
| `all` | AND: every nested condition must match | `conditions:` a list |
| `any` | OR: at least one must match | `conditions:` a list |
| `not` | NOT: matches if the nested condition does *not* | `condition:` a single one |

Groups can be nested as deep as you like:

```yaml
rules:
  - name: Unread mail from my boss or from anyone about an outage, but not newsletters
    locations: [{account_id: 6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11}]
    when:
      type: all
      conditions:
        - type: bool
          field: seen
          value: false
        - type: any
          conditions:
            - type: address
              field: from
              operator: equals
              value: boss@example.com
            - type: text
              field: subject
              operator: contains
              value: outage
        - type: not
          condition:
            type: bool
            field: has_list_unsubscribe
```

### Text conditions: `type: text`

Checks a text field such as the subject or the body.

```yaml
type: text
field: subject
operator: contains
value: invoice
case_sensitive: false      # optional, the default
```

| Operator | Matches when the text ... |
|---|---|
| `equals` | is exactly the value |
| `contains` | has the value somewhere inside |
| `startswith` | begins with the value |
| `endswith` | ends with the value |
| `regex` | has a match for the regular expression (it searches, use `^` and `$` to anchor) |
| `glob` | fits a pattern with `*` (anything) and `?` (one character), e.g. `*.pdf` |
| `in` | is exactly one of a list of values, `value: [a, b, c]` |

**Case sensitivity:** `case_sensitive` works for *every* text operator, including `regex`.
It is `false` by default, so `Invoice`, `INVOICE` and `invoice` all match `invoice`.
Set it to `true` to care about capitals.

```yaml
- type: text
  field: subject
  operator: regex
  value: '^\[JIRA\] (BUG|TASK)-\d+'
  case_sensitive: true
```

### Addresses: `type: address`

Like a text condition, but for fields that hold email addresses, and with a `part`:
you choose how much of the address is compared.

Take `Max Mustermann <m.muster@example.com>`:

| `part` | Compared text |
|---|---|
| `full` | `Max Mustermann <m.muster@example.com>` |
| `name` | `Max Mustermann` |
| `address` (default) | `m.muster@example.com` |
| `local_part` | `m.muster` |
| `domain` | `example.com` |

```yaml
- type: address
  field: from
  part: domain
  operator: in
  value: [example.com, example.org]
```

### Numbers: `type: number`

```yaml
type: number
field: size
operator: gt
value: 5000000            # bytes
```

| Operator | Means |
|---|---|
| `eq` / `ne` | equal / not equal |
| `lt` / `gt` | less than / greater than |
| `lte` / `gte` | less than or equal / greater than or equal |
| `between` | inside a range, both ends included, `value: [low, high]` |

### Dates and times: `type: date`

Uses the same operators as numbers, applied to `date_sent` or `date_received`.
The value is either a fixed moment or a time span counted back from now.
Write which one with `relative`:

```yaml
# a fixed moment (no time zone means UTC)
- type: date
  field: date_received
  operator: gte
  value: {relative: false, value: '2026-01-01T00:00:00+00:00'}

# older than a week: "received before the moment 7 days ago"
- type: date
  field: date_received
  operator: lt
  value: {relative: true, value: 7d}

# received during the last 2 days and 12 hours, i.e. between two relative moments
- type: date
  field: date_received
  operator: between
  value:
    - {relative: true, value: 60h}
    - {relative: true, value: 0s}
```

Time spans are a number plus a unit: `s` seconds, `m` minutes, `h` hours, `d` days, `w` weeks.
Note the direction: `7d` means *the moment 7 days ago*, so `lt` is "older than" and `gt` is "newer than".

### Yes or no: `type: bool`

Fields that are either true or false, like read or unread.
`value` is what you want it to be and defaults to `true`.

```yaml
- type: bool
  field: seen
  value: false        # unread
```

### Is it there at all: `type: presence`

Checks whether a field or header exists, using `field` or `header` (exactly one of them).

```yaml
- type: presence
  header: X-Mailer             # has an X-Mailer header
- type: presence
  field: list_id
  value: false                 # has no List-Id
- type: presence
  header: X-Spam-Flag
  operator: empty              # there, but without any text
```

### Any header: `type: header`

For anything without a dedicated field, a custom header by its name.
It takes the same keys as `text`, with `name` instead of `field`.
The name is not case sensitive.

```yaml
- type: header
  name: X-Priority
  operator: equals
  value: '1'
```

### Several values: `quantifier`

Some things exist more than once in a mail: recipients, attachments, headers sent twice.
`quantifier` says how many of them have to match, and works on `text`, `address`, `number`, `bool` and `header` conditions:

| `quantifier` | Matches when ... |
|---|---|
| `any` (default) | at least one of them matches |
| `all` | every one of them matches |
| `none` | not a single one matches |

```yaml
# every recipient is at example.com
- type: address
  field: recipients
  part: domain
  operator: equals
  value: example.com
  quantifier: all
```

### Missing things never match

If a mail simply does not have what the condition looks at (no spam header, no HTML part, no attachments) the condition is **false**, whatever the operator.
This includes "negative" operators: `ne` or a `regex` like `^(?!x)` do not match a mail that lacks the field.
To select such mails, say so explicitly with `presence` and `value: false`, or wrap the condition in `not`.

## The fields

### Standard stuff

| Field (type) | Meaning |
|---|---|
| `account_id` (text) | The account the mail is in. |
| `folder` (text) | The folder the mail is in. |
| `from` (address) | The sender shown on the mail. |
| `sender` (address) | The `Sender:` header, if somebody sent on behalf of the `from` address. |
| `reply_to` (address) | Where replies go (`Reply-To:`). |
| `return_path` (address) | The bounce address. |
| `to`, `cc`, `bcc` (address) | The receivers. |
| `recipients` (address) | `to`, `cc` and `bcc` together. |
| `delivered_to` (address) | The address the mail was finally delivered to, useful for aliases. |
| `subject` (text) | The subject line. |
| `body_text` (text) | The plain text body. |
| `body_html` (text) | The HTML body, raw HTML. It is separate: `body_text` does not turn into HTML, and vice versa. Use `presence` to check which exist. |
| `seen` (bool) | **Read.** Use `value: false` for **unread**. |
| `flagged` (bool) | Starred / flagged. |
| `answered` (bool) | Has been replied to. |
| `draft` (bool) | Is a draft. |
| `deleted` (bool) | Marked as deleted. |
| `keywords` (text) | Custom labels set on the mail (IMAP keywords like `$Important`), without the built-in flags above. |
| `date_sent` (date) | The date the sender wrote on the mail. |
| `date_received` (date) | When your server received it. Harder to fake than `date_sent`. |
| `size` (number) | Total size in bytes. |
| `uid` (number) | The mail's number in its folder. |
| `mime_type` (text) | The top level type, e.g. `multipart/mixed`. |

The body fields are only downloaded when a rule actually uses them, so rules on other fields stay fast.

### Spam

| Field (type) | Meaning |
|---|---|
| `spam_score` (number) | The score your mail server gave. Read from the first of `X-Spam-Score`, `X-Rspamd-Score`, `X-Spam-Status` (`score=...`) or `X-Spam-Level` (the number of stars). |
| `spam_flag` (bool) | The server's verdict: `X-Spam-Flag`, or else `X-Spam-Status` starting with `Yes`. |
| `auth_spf`, `auth_dkim`, `auth_dmarc` (text) | The sender checks from `Authentication-Results`, e.g. `pass`, `fail`, `none`. |

### Attachments

Each attachment counts as one value, so `quantifier` applies.

| Field (type) | Meaning |
|---|---|
| `attachments_count` (number) | How many attachments. |
| `attachment_size` (number) | Size of each attachment in bytes. |
| `attachment_mime_type` (text) | File type of each, e.g. `application/pdf`, `image/png`. |
| `attachment_filename` (text) | File name of each. |
| `attachment_extension` (text) | The extension of each without the dot, lower case, e.g. `pdf`. |
| `attachment_inline` (bool) | Whether each is shown inside the mail (like a logo) instead of being a download. |

### Newsletters, replies and automatic mail

| Field (type) | Meaning |
|---|---|
| `has_list_unsubscribe` (bool) | Has an unsubscribe header: a good sign of a newsletter. |
| `list_id` (text) | The mailing list id. |
| `is_reply` (bool) | Is an answer to another mail. |
| `in_reply_to`, `references`, `message_id` (text) | The headers that link mails to conversations. |
| `auto_submitted` (text) | Set (e.g. `auto-replied`) on automatic mails and out-of-office replies. |
| `precedence` (text) | `bulk` or `list` on mass mail. |
| `importance` (text) | The importance the sender requested. |

Anything not on these lists can be read with a `header` condition.

### Technical

| Field (type) | Meaning |
|---|---|
| `modseq` (number) | A counter that grows with every change of the mail on the server, not a time. IMAP does not record a "last modified" date. Only available if the server supports CONDSTORE. |

## Cookbook

Each snippet is the `when:` part of a rule.

**Unread mails**

```yaml
when: {type: bool, field: seen, value: false}
```

**Unread mail from a sender, any capitalization**

```yaml
when:
  type: all
  conditions:
    - {type: bool, field: seen, value: false}
    - {type: address, field: from, operator: equals, value: Max.Muster@Example.com}
```

**Everything from a whole company's domain**

```yaml
when: {type: address, field: from, part: domain, operator: endswith, value: example.com}
```

**Sent directly to me, not via a list or Bcc** (using the `to` address)

```yaml
when:
  type: all
  conditions:
    - {type: address, field: to, operator: equals, value: me@example.com}
    - {type: presence, field: list_id, value: false}
```

**Likely spam that the server did not flag**

```yaml
when:
  type: all
  conditions:
    - {type: number, field: spam_score, operator: gte, value: 5}
    - {type: bool, field: spam_flag, value: false}
```

**Failed the sender checks**

```yaml
when:
  type: any
  conditions:
    - {type: text, field: auth_spf, operator: equals, value: fail}
    - {type: text, field: auth_dkim, operator: equals, value: fail}
```

**Mails with at least one PDF over 1 MB**

```yaml
when:
  type: all
  conditions:
    - {type: text, field: attachment_extension, operator: equals, value: pdf}
    - {type: number, field: attachment_size, operator: gt, value: 1000000}
```

Both conditions are checked on *some* attachment each, so this can also match a mail with a small PDF and a big picture.
If you need "a PDF that is also big", that is a limit of the current rules: conditions on different attachment fields are not tied to the same attachment.

**More than three attachments**

```yaml
when: {type: number, field: attachments_count, operator: gt, value: 3}
```

**Only images as attachments**

```yaml
when:
  type: all
  conditions:
    - {type: number, field: attachments_count, operator: gt, value: 0}
    - {type: text, field: attachment_mime_type, operator: startswith, value: 'image/', quantifier: all}
```

**Old, read mail over 10 MB (candidates for cleanup)**

```yaml
when:
  type: all
  conditions:
    - {type: bool, field: seen}
    - {type: number, field: size, operator: gt, value: 10000000}
    - {type: date, field: date_received, operator: lt, value: {relative: true, value: 52w}}
```

**Newsletters except from people I know**

```yaml
when:
  type: all
  conditions:
    - {type: bool, field: has_list_unsubscribe}
    - type: not
      condition: {type: address, field: from, part: domain, operator: in, value: [example.com, example.org]}
```

**A custom header**

```yaml
when: {type: header, name: X-GitHub-Reason, operator: equals, value: review_requested}
```

**Mail that has HTML but no plain text part**

```yaml
when:
  type: all
  conditions:
    - {type: presence, field: body_html}
    - {type: presence, field: body_text, value: false}
```

**Mails between 1 January and 1 February 2026**

```yaml
when:
  type: date
  field: date_sent
  operator: between
  value:
    - {relative: false, value: '2026-01-01T00:00:00+00:00'}
    - {relative: false, value: '2026-02-01T00:00:00+00:00'}
```

## Templates: the same rule for many senders

Rules that differ only in a few values can share one definition.
Put it under the root `templates`, mark the replaceable fields with `{var: name}` (or the shorthand `!var name`), and give the definition a YAML anchor.
Use it anywhere an expression is allowed with the merge key `<<: *anchor` and fill in `variables`.
`defaults` of the definition are used for variables the use does not set.

```yaml
templates:
  anonaddy-forward: &anonaddy-forward
    type: template
    defaults:
      sender_name: " 'notifications at github.com'"
    content:
      type: all
      conditions:
        - {type: address, field: from, part: address, operator: equals, value: {var: alias}}
        - {type: address, field: from, part: name, operator: endswith, value: {var: sender_name}}

rules:
  - name: Mark GitHub mail as read
    locations:
      - account_id: 6f1c1d0e-5a52-4f6c-9a4e-0f7a6b2f3a11
    when:
      <<: *anonaddy-forward
      variables:
        alias: github.com-example@anonaddy.io
    actions:
      - type: mark_read
```

- Every variable needs a value in `variables` or `defaults`, and `variables` must not name a variable the template does not use, both are errors.
- Any field can be a variable, also numbers, operators or whole sub-expressions, and a template can use other templates.
- Templates are resolved when the file is loaded, the result is the same as writing the rules out by hand.

## Actions

What to do with a matching mail.
These are validated already, but not executed yet.

| `type` | Does | Keys |
|---|---|---|
| `move` | Moves the mail, also into another account | `folder`, optional `account_id` (the mail's own account if left out) |
| `mark_read` | Sets the read flag | |
| `mark_unread` | Removes the read flag | |
| `flag` | Stars the mail, or removes the star | `value` (default `true`) |
| `keyword` | Adds or removes a custom label | `keyword`, `value` (default `true`) |

```yaml
actions:
  - type: move
    folder: Archive/Invoices
    account_id: 0b8d3f4c-2b6e-4f0e-8f4a-3c8f6f1e9d22
  - type: mark_read
```

## Not built yet

These ideas from the project plan are not part of the rules file itself and do not exist yet:

- The visual rule editor, including creating a rule from a mail ("mail first": the conditions are pre-filled with that mail's sender, subject and so on, with a choice of detail such as name and address, only the address, or only the name) or filling a condition from a mail ("rule first").
- The log of everything that happened to a mail.
- Rules across providers beyond one account per run, and running the actions.
