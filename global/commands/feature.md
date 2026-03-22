---
description: "Plan and scaffold a new feature. Runs an analyst conversation, then creates a GitHub issue and branch. Use 'propose <title>' to skip analysis and just note the idea (no local checkout)."
allowed-tools: Agent, Bash, Read, Glob, Grep
---

You are orchestrating a feature planning workflow.

Check `$ARGUMENTS`:
- If it starts with `propose`, strip the word "propose" and run the **Propose flow** below.
- Otherwise, run the **Full flow** below.

---

## Propose flow (`/feature propose <title>`)

A lightweight path for jotting down ideas without switching context.

Follow the `/issue` flow exactly — draft the issue, iterate with the user, then hand off to gh-agent — but pass `checkout=false` so no local branch switch occurs.

---

## Full flow (`/feature <idea>`)

### Step 1: Analysis

Invoke the analyst-agent with the feature idea: $ARGUMENTS

### Step 2: Handoff

Once the user has confirmed the feature description with the analyst-agent, invoke the gh-agent with the approved description (checkout=true).

### Step 3: Done

The gh-agent will report the issue URL and branch. Relay this to the user.

