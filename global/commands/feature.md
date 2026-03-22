---
description: "Plan and scaffold a new feature. Runs an analyst conversation, then creates a GitHub issue, branch, and worktree. Use 'propose <title>' to skip analysis and just note the idea (no local checkout)."
allowed-tools: Agent, Bash, Read, Glob, Grep, EnterWorktree, ExitWorktree
---

You are orchestrating a feature planning workflow.

Check `$ARGUMENTS`:
- If it starts with `propose`, strip `propose` and run the **Propose flow** below.
- If it starts with `push`, run the **Push flow** below.
- If it starts with `merge checkout`, run the **Merge checkout flow** below.
- Otherwise, run the **Full flow** below.

---

## Propose flow (`/feature propose <title>`)

A lightweight path for jotting down ideas without switching context.

Draft the issue title and body, iterate with the user until they confirm, then invoke gh-agent directly with `checkout=false` so no local branch switch occurs.

---

## Push flow (`/feature push`)

Invoke gh-agent with `merge` to create a pull request from the current branch against the default branch.

---

## Merge checkout flow (`/feature merge checkout`)

1. Invoke gh-agent with `merge approve checkout` to merge the open PR.
2. Call `ExitWorktree` with `action=remove` to return to the main directory and remove the worktree.
3. Pull the default branch:
   ```bash
   git pull
   ```

---

## Full flow (`/feature <idea>`)

### Step 1: Analysis

Invoke the analyst-agent with the feature idea: $ARGUMENTS

### Step 2: GitHub handoff

Once the user has confirmed the feature description with the analyst-agent:

1. Invoke gh-agent with the approved description and `checkout=false`. Capture the branch name returned (e.g. `feat/42-my-feature`).
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
