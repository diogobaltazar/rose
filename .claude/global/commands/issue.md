---
description: Draft, iterate on, and create a GitHub issue, then branch and checkout before implementing
allowed-tools: Bash, Read, Glob, Grep
---

You are helping the user define a well-scoped GitHub issue before any implementation begins.

Additional context or idea from user: $ARGUMENTS

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

### 3. Create the issue

Once approved, run:

```
gh issue create --title "<title>" --body "<body>"
```

Capture the issue URL and number from the output.

### 4. Create and checkout the branch

Derive a slug from the title: lowercase, spaces to hyphens, strip special characters, max ~5 words.

```
git checkout -b {number}-{slug}
```

e.g. `git checkout -b 42-add-docker-compose`

Confirm to the user: "Issue #{number} created. Branch `{number}-{slug}` checked out. Ready to implement."

### 5. Begin implementation

Only now start writing code. Follow the project's Definition of Done throughout.
