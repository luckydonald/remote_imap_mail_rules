---
name: pinia-not-inject
description: "Frontend global state belongs in Pinia stores called via useStore() in each file, not provide/inject or lifting it into AppShell"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 24854bb1-25a0-4576-9b3e-7fe156df1ffa
  modified: 2026-11-04T15:57:54.592Z
---

Use Pinia stores directly (`useXStore()` in every component that needs it), not provide/inject and not lifting a store up into `AppShell` to pass it down.

**Why:** the user rejected a plan that lifted the rule store into the shell so the mail view could reach it; they consider a per-file `useStore()` the proper Pinia way.

**How to apply:** per-subtree flags (like `ALLOW_VARS`) may stay as injection keys, but anything global (rule store, prefs, mail store) is a `defineStore`. See [[feedback_playwright_not_chrome]] for how the frontend is verified.
