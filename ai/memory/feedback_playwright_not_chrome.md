---
name: playwright-not-chrome
description: "Verify frontend behavior with Playwright tests in the repo, not by driving Chrome through the claude-in-chrome tools"
metadata:
  node_type: memory
  type: feedback
  originSessionId: f43777df-eee9-4e2b-83ab-54194a64e794
  modified: 2026-11-03T11:18:50.718Z
---

For checking the frontend in a browser, write Playwright tests (`frontend/e2e/`, `yarn test:e2e`) instead of using the claude-in-chrome tools.

**Why:** The user rejected a plan that used Chrome tooling: "Write playwright tests instead, no chrome claude."
Tests stay in the repo and rerun; manual browser driving does not.

**How to apply:** Any "look at it in a browser" or UI verification task becomes an e2e spec.
See [[repo_commit_hooks]] for the commit flow around it.
