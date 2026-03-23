---
description: "Feature workflow. Subcommands: propose <title>, work <description>, push, merge, merge checkout. Bare '/feature <description>' is an alias for '/feature work <description>'."
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
- Otherwise (bare description with no subcommand), treat as `/feature work $ARGUMENTS` and run the **Work flow**.

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

## Full planning flow (`/feature <idea>` — no subcommand, treated as work)

### Step 1: Analysis

Invoke the analyst agent in **Feature Analysis mode** with the feature idea.

### Step 2: GitHub handoff

Once the user has confirmed the feature description with the analyst:

1. Invoke the github agent with the approved description and `checkout=false`. Capture the branch name returned (e.g. `feat/42-my-feature`).
2. Call `EnterWorktree` with `name=<branch-name>` — this creates a worktree and switches the session into it.
3. Inside the worktree, rename the branch to match and push:
   ```bash
   git branch -m <branch-name>
   git push -u origin HEAD
   ```

### Step 3: Done

Report to the user:
- The GitHub issue URL and branch name
- That the session is now inside the worktree and ready to work
