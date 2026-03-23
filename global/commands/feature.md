---
description: "Feature workflow. Subcommands: propose <title>, work <description>, push, merge, merge checkout. Bare '/feature <description>' runs the full planning flow."
allowed-tools: Agent, Bash, Read, Glob, Grep, EnterWorktree, ExitWorktree
---

You are orchestrating a feature planning workflow.

Check `$ARGUMENTS`:
- If it starts with `propose`, strip `propose` and run the **Propose flow** below.
- If it starts with `work`, strip `work` and run the **Work flow** below.
- If it starts with `push`, run the **Push flow** below.
- If it starts with `merge checkout`, run the **Merge checkout flow** below.
- If it starts with `merge`, run the **Merge flow** below.
- If `$ARGUMENTS` is empty, print usage and stop.
- Otherwise (bare description with no subcommand), run the **Full planning flow** below.

---

## Propose flow (`/feature propose <title>`)

A lightweight path for jotting down ideas without switching context.

Draft the issue title and body, iterate with the user until they confirm, then invoke the github agent directly with `checkout=false` so no local branch switch occurs.

---

## Work flow (`/feature work <description>`)

Implement a feature end-to-end, from spec reconciliation through to a committed result.

### Step 1: Spec reconciliation

Invoke the analyst agent in **Spec Reconciliation mode** with the feature description. The analyst will:
- Read `CLAUDE.md` and evaluate the feature against existing product specifications.
- Update `CLAUDE.md` or surface a conflict for the user to resolve.
- Return the reconciled specification.

### Step 2: Implementation

Once the analyst confirms spec reconciliation is complete, invoke the engineer agent with the reconciled specification. The engineer will implement the feature and invoke `/git commit` when done.

---

## Push flow (`/feature push`)

Invoke the github agent with `merge` to create a pull request from the current branch against the default branch.

---

## Merge flow (`/feature merge`)

Invoke the github agent with `merge` to create a pull request from the current branch against the default branch.

---

## Merge checkout flow (`/feature merge checkout`)

1. Invoke the github agent with `merge approve checkout` to merge the open PR.
2. Call `ExitWorktree` with `action=remove` to return to the main directory and remove the worktree.
3. Pull the default branch:
   ```bash
   git pull
   ```

---

## Full planning flow (`/feature <description>` — no subcommand)

### Step 0 — Entry point detection

Classify the user's description by scanning for keywords:
- **E2** if the description contains any of: `bug`, `broken`, `error`, `failing`, `fix`
- **E3** if the description contains any of: `upgrade`, `bump`, `dependency`, `version`
- **E4** if the description contains any of: `investigate`, `research`, `spike`, `explore`, `question`
- **E1** otherwise (default)

### Step 1 — Invoke analyst in Feature Analysis mode

Invoke the analyst agent in **Feature Analysis mode**, passing:
- The user's description
- The detected entry point code (E1, E2, E3, or E4)
- Instruction to execute R1 → R2 → R3 → R4 → R5 in order, then return either:
  - `"investigation"` + a write-up (W1)
  - `"delivery"` + the reconciled specification

### Step 2 — Decision gate

- If the analyst returns `"investigation"`: the pipeline ends. Report the write-up to the user.
- If the analyst returns `"delivery"`: continue to Step 3.

### Step 3 — D1: GitHub feature setup

Invoke the github agent in **Feature Setup** mode with the confirmed spec. Capture the issue URL and branch name returned.

### Step 4 — D2: Enter worktree

Call `EnterWorktree` with `name=<branch-name>` to create a worktree and switch the session into it. Inside the worktree, rename the branch to match and push:

```bash
git branch -m <branch-name>
git push -u origin HEAD
```

### Step 5 — Report

Report to the user:
- The GitHub issue URL and branch name
- That the session is now inside the worktree and ready to work
