---
description: Draft, iterate on, and create a GitHub issue, then branch and checkout before implementing
allowed-tools: Agent, Bash, Read, Glob, Grep
---

You are helping the user define a well-scoped GitHub issue before any implementation begins.

Additional context or idea from user: $ARGUMENTS

If `$ARGUMENTS` contains `checkout=false`, strip it from the idea text and set `checkout=false` for Step 3. Otherwise default to `checkout=true`.

## Steps

### 1. Draft the issue

Based on the conversation so far (and $ARGUMENTS if provided), write a draft GitHub issue in this format:

---
**Title:** [concise imperative title, e.g. "Add docker compose setup"]

**Description:**
[1-2 sentences on what this is and why it matters]

**Scope / what this includes:**
- [bullet list of what will be done]

**Out of scope:**
- [what is explicitly NOT included to keep this focused]

**Acceptance criteria:**
- [ ] [observable, testable criterion]
- [ ] [...]

**Technical notes:**
[Any relevant implementation pointers, file locations, constraints — optional]
---

### 2. Iterate

Show the draft to the user and ask: "Does this look right, or would you like to adjust anything?"

Keep iterating — updating the draft in full each time — until the user explicitly approves it (e.g. "looks good", "ship it", "go ahead").

### 3. Hand off to gh-agent

Once approved, invoke the `gh-agent` via the Agent tool, passing:
- The full issue title and body
- `checkout=true` or `checkout=false` (from the flag parsed above)

gh-agent will create the GitHub issue, create the branch, and (if `checkout=true`) check it out locally. Wait for its confirmation before proceeding.

### 4. Begin implementation (checkout=true only)

Only if `checkout=true`: now start writing code. Follow the project's Definition of Done throughout.

If `checkout=false`: confirm the issue and branch were created, and let the user know they can pick it up later.
