---
description: "Plan and scaffold a new feature. Runs an analyst conversation, then creates a GitHub issue and branch. Use 'propose <title>' to skip analysis and just note the idea (no local checkout)."
allowed-tools: Agent, Bash, Read, Glob, Grep
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

Invoke gh-agent with `merge approve checkout` to merge the open PR, pull the default branch, check it out locally, and delete the feature branch.

---

## Full flow (`/feature <idea>`)

### Step 1: Analysis

Invoke the analyst-agent with the feature idea: $ARGUMENTS

### Step 2: GitHub handoff

Once the user has confirmed the feature description with the analyst-agent, invoke the gh-agent with the approved description (checkout=true).

### Step 3: Done

Report to the user:
- The GitHub issue URL and branch name
