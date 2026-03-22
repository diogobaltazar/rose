---
description: "Project-level Claude configuration. Subcommands: init — scaffold .claude/ in a project. config — add agents, skills, or CLAUDE.md entries to the current project's .claude/ directory."
allowed-tools: Agent, Read, Glob, Grep, Bash
---

You are orchestrating project-level Claude configuration.

Parse `$ARGUMENTS`:
- If it starts with `init`, strip `init` and run the **Init flow** below.
- If it starts with `config`, strip `config` and run the **Config flow** below.
- Otherwise, tell the user the available subcommands: `init`, `config`.

---

## Init flow (`/project init`)

Scaffold a `.claude/` directory in the current working directory.

1. Check if `.claude/` already exists — if so, tell the user and stop.
2. Create `.claude/CLAUDE.md` with the following template (replace `{project_name}` with the directory name):

```markdown
# {project_name}

## Overview
[What this project does in 2–3 sentences.]

## Tech stack
[Languages, frameworks, key dependencies.]

## Common commands
\```
test:   [command]
build:  [command]
lint:   [command]
\```

## Project structure
[Key directories and what lives in them.]

## Conventions
[Coding conventions, naming rules, anything Claude should know.]
```

3. Create `.claude/settings.json` with contents `{}`.
4. Tell the user what was created and to edit `.claude/CLAUDE.md` to add project-specific context.

---

## Config flow (`/project config <what you want>`)

Invoke `project-conf-agent` with the user's request.

The agent will:
1. Inspect the current project (stack, existing `.claude/` contents)
2. Converse with the user to understand what they want
3. Create the appropriate files inside `.claude/` of the current project

When the agent is done, summarise what was created for the user.

### Important context to pass to the agent

- All writes go to `.claude/` in the current working directory — the project Claude is open in.
- If Claude is running inside the rose repo, `.claude/` here means `rose/.claude/` — **not** `rose/global/`. Files written here are project-specific and are not installed globally by `rose install`.
- Never modify `~/.claude/` or `rose/global/`.
