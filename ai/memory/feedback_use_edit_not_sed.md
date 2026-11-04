---
name: feedback-use-edit-not-sed
description: "macOS has BSD sed, so `sed -i 'expr' file` fails; use the Edit tool for file changes instead of sed"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 4cd24740-a34e-4318-aaed-5bfb7ce17742
  modified: 2026-11-04T03:15:56.306Z
---

Use the Edit tool for changing files, not `sed -i`.

**Why:** the machine is macOS (Darwin) with BSD sed, where `sed -i` needs a backup suffix argument (`-i ''`).
`sed -i 's|a|b|' file` fails with "invalid command code" and changes nothing, which cost a wasted round trip while editing `MailLogin.vue`.

**How to apply:** for any edit of a tracked file reach for Edit first.
If a scripted bulk change is really needed, use a small Python script, in line with [[feedback-scripts-python-uv]], rather than sed.
