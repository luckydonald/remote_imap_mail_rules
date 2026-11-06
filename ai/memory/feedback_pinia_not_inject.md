---
name: pinia-not-inject
description: "Frontend has ONE central Pinia store (useStore), composed from plain function files; no provide/inject, no extra stores per concern"
metadata:
  node_type: memory
  type: feedback
  originSessionId: 24854bb1-25a0-4576-9b3e-7fe156df1ffa
  modified: 2026-11-06T15:38:28.669Z
---

Global frontend state lives in one central Pinia store, `useStore()` (`frontend/src/model/store/index.ts`), called directly in every component that needs it.
Not provide/inject, not lifting a store into `AppShell` to pass it down, and not a new `defineStore` per concern.

**Why:** the earlier rule ("Pinia stores directly, `useX()` per file") was misread as "one store per problem", which produced five stores (rules, mail, prefs, clipboard, menu) that reached into each other and a duplicate account fetch in the log screen. The user wants everything about mails and rules in one store, with a second one only for a really unrelated concern.

**How to apply:** new global state is a plain function in its own file under `model/store/` (returns refs and functions, takes shared parts like `prefs` as arguments) and is spread into the one `defineStore` in `index.ts`; give the names specific enough not to clash (`openMenu`, `cutBlock`). Data the store owns (accounts, `actionsEnabled`) is read through it, a screen never fetches it again. Per-subtree flags (like `ALLOW_VARS`) may stay injection keys and component-local `ref`s stay local. If a second store seems warranted, ask first. See [[feedback_playwright_not_chrome]] for how the frontend is verified.
