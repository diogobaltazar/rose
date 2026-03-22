---
description: "GitHub operations on the current branch. Usage: /gh merge | /gh merge approve checkout"
allowed-tools: Agent, Bash
---

GitHub operations on the current repository.

Operation: $ARGUMENTS

Invoke gh-agent with the operation: $ARGUMENTS

- `merge` — create a pull request from the current branch against the default branch
- `merge approve checkout` — merge the open PR, pull the default branch, and check it out locally (requires admin privileges)
