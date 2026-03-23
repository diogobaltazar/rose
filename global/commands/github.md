---
description: "GitHub operations on the current branch. Usage: /github merge | /github merge approve checkout | /github issue <description>"
allowed-tools: Agent, Bash
---

GitHub operations on the current repository.

Operation: $ARGUMENTS

Parse `$ARGUMENTS`:
- If it starts with `issue`, strip `issue` and run the **Issue flow** below.
- Otherwise, invoke the github agent with the full operation string.

## Operations (non-issue)

- `merge` — create a pull request from the current branch against the default branch
- `merge approve checkout` — merge the open PR, pull the default branch, and check it out locally (requires admin privileges)

## Issue flow (`/github issue <description>`)

Invoke the github agent in feature-setup mode with the description provided. Pass `checkout=true` so a branch is created and checked out locally.

No drafting, no iteration — just create the issue and branch immediately.
