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

### Step 1: Check for existing feature agents

Before doing anything, check whether `.claude/commands/` already contains a command file matching the feature slug (lowercase, hyphenated form of the feature idea). If it does, this is a **reassessment run** — skip to Step 4.

### Step 2: Analysis

Invoke the analyst-agent with the feature idea: $ARGUMENTS

### Step 3: GitHub handoff

Once the user has confirmed the feature description with the analyst-agent, invoke the gh-agent with the approved description (checkout=true).

### Step 4: Scaffold or reassess feature agents

**On every `/feature` run** — whether this is a new feature or an existing one — invoke `project-conf-agent` with the following instructions:

> "Scaffold (or reassess) the feature agents for: <feature title>
>
> Feature description: <confirmed description from analyst, or the original $ARGUMENTS if reassessing>
>
> Feature slug: <slug>
>
> If `.claude/commands/<slug>.md` does not exist, scaffold the full set:
> - `.claude/commands/<slug>.md` — orchestrating command
> - `.claude/agents/<slug>-analyst.md`
> - `.claude/agents/<slug>-engineer.md`
> - `.claude/agents/<slug>-tester.md`
>
> If those files already exist, reassess the feature's complexity against the current codebase and update the `model` fields if the complexity tier has changed. Report what changed and why.
>
> In both cases, assess complexity and choose models deliberately before writing."

### Step 5: Done

Report to the user:
- The GitHub issue URL and branch name (if this was a new feature)
- The files created or updated by `project-conf-agent`

