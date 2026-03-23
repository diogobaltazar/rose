---
description: "Project setup and spec management. Subcommands: init, spec update <specification>."
allowed-tools: Agent, Read, Write, Bash, Glob
---

You are orchestrating project-level setup and specification management.

Parse `$ARGUMENTS`:
- If it starts with `init`, run the **Init flow** below.
- If it starts with `spec update`, strip `spec update` and run the **Spec Update flow** below.
- Otherwise, tell the user the available subcommands: `init`, `spec update <specification>`.

---

## Init flow (`/project init`)

Scaffold a `CLAUDE.md` and `.claude/` directory in the current working directory.

1. Check whether `CLAUDE.md` already exists. If it does and `--force` is not in `$ARGUMENTS`, inform the user and skip creating it.
2. Check whether `.claude/settings.json` already exists. If it does and `--force` is not in `$ARGUMENTS`, inform the user and skip creating it.
3. Create `CLAUDE.md` with the following minimal template (if it does not exist or `--force` is set):
   ```markdown
   # <project name>

   ## Product Specifications

   *(No specifications yet. Use `/project spec update <specification>` to add them.)*
   ```
   Use the current directory name as the project name.
4. Create `.claude/settings.json` as an empty JSON object `{}` (if it does not exist or `--force` is set).
5. Report what was created or skipped.

---

## Spec Update flow (`/project spec update <specification>`)

Invoke the analyst agent in **Spec Reconciliation mode** with the following instruction:

"Read CLAUDE.md in the current directory. Incorporate the following specification into it, creating or updating sections as you see fit. There is no fixed schema — use your judgement to organise the content clearly. If a conflict exists with an existing specification, surface it to the user before making any changes. Specification: <the remaining arguments>"
