# Claude Code configuration reference

This document explains every file and concept behind the `.claude/` configuration tree. Rose is built on top of these primitives. Understanding them lets you extend or replace any part of the setup.

## Two config scopes

Claude Code has two distinct config locations that layer on top of each other:

| Scope | Location | Loaded |
|-------|----------|--------|
| **Global** | `~/.claude/` | Every Claude Code session on this machine |
| **Project** | `<project>/.claude/` | Only when Claude is opened inside that project directory |

Global config sets up the agent's baseline behaviours (global agents, slash commands). Project config adds project-specific context on top (component agents, `CLAUDE.md`).

---

## `~/.claude/` — global config tree

```
~/.claude/
├── CLAUDE.md              # Global persona and tone (read every session)
├── settings.json          # Core configuration: env vars
├── agents/                # Global subagents available in every session
│   ├── git-agent.md
│   ├── analyst-agent.md
│   ├── gh-agent.md
│   └── project-conf-agent.md
└── commands/              # Slash commands available in every session
    ├── git.md
    ├── gh.md
    ├── feature.md
    └── project.md
```

---

## `settings.json`

The main config file. Supports one top-level key: `env`.

```json
{
  "env": { ... }
}
```

### `env`

Key-value pairs injected as environment variables into every Claude Code session. Use this for API base URLs, auth tokens, and custom HTTP headers — anything that varies per machine or user but shouldn't live in code.

```json
"env": {
  "ANTHROPIC_BASE_URL": "http://localhost:8080",
  "ANTHROPIC_AUTH_TOKEN": "dummy-gateway-token",
  "ANTHROPIC_CUSTOM_HEADERS": "x-portkey-metadata: {...}"
}
```

---

## CLI (`rose`)

The `rose` CLI manages the global config installation. It runs inside the rose Docker container and mounts `~/.claude` from the host.

| Command | Description |
|---------|-------------|
| `rose install` | Copy global config from the image into `~/.claude/` |
| `rose reinstall` | Wipe `~/.claude/` and reinstall from scratch |
| `rose uninstall` | Remove the installed global config from `~/.claude/` |

Project-level configuration (scaffolding `.claude/` inside a project, configuring agents and commands) is handled by Claude itself via the `/project` slash command — not the CLI.

---

## Agents

Agents are subprocesses that Claude can spawn to handle specific tasks. They run as independent Claude instances with their own tool access and system prompt.

An agent is defined by a Markdown file with a YAML frontmatter header:

```markdown
---
name: my-agent
description: One-line summary used by Claude to decide when to invoke this agent
model: sonnet          # claude model: sonnet | opus | haiku
tools: Read, Write, Edit, Bash, Glob, Grep
---

The system prompt for the agent goes here.
Markdown formatted. Can be as long as needed.
```

**Frontmatter fields:**

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Identifier used to reference the agent |
| `description` | Yes | Claude reads this to decide whether to invoke the agent. Write it as a usage hint: "Use when X", "Handles Y" |
| `model` | No | Which Claude model to use. Defaults to the session model |
| `tools` | No | Comma-separated list of tools the agent can use. Restricting tools limits blast radius |

**Agent placement:**

- `~/.claude/agents/` — global agents, available in every session
- `<project>/.claude/agents/` — project agents, available only within that project

**How Claude invokes agents:**

Claude sees all available agents' `name` and `description` fields in its context. When a task matches an agent's description, Claude spawns it via the `Agent` tool, passing a prompt. The agent runs to completion and returns a result.

**Rose's global agents:**

| Agent | Description |
|-------|-------------|
| `git-agent` | Executes git operations sequentially (commit, push) |
| `analyst-agent` | Researches codebase and web, asks clarifying questions, proposes feature descriptions |
| `gh-agent` | Creates GitHub issues, manages branches and pull requests |
| `project-conf-agent` | Inspects a project's stack and scaffolds or reassesses feature agents in `.claude/` |

---

## Commands (slash commands)

Slash commands are user-invocable shortcuts. Typing `/git` in a Claude Code session triggers the corresponding command file.

A command is a Markdown file with frontmatter:

```markdown
---
description: Short description shown in the command picker
allowed-tools: Bash, Read, Glob, Grep
---

The prompt that gets injected when the user runs this command.
Use $ARGUMENTS to capture anything the user types after the command name.
```

**Frontmatter fields:**

| Field | Description |
|-------|-------------|
| `description` | Shown in the `/` picker UI |
| `allowed-tools` | Tools Claude may use when executing this command |

**`$ARGUMENTS`** is replaced with everything the user typed after the command name. For example, `/git commit push` sets `$ARGUMENTS` to `commit push`.

**Command placement:**

- `~/.claude/commands/` — global commands, available in every session
- `<project>/.claude/commands/` — project-scoped commands

**Rose's global commands:**

| Command | What it does |
|---------|-------------|
| `/git` | Invokes `git-agent` to run git operations sequentially (commit, push) |
| `/gh` | GitHub operations: `merge`, `merge approve checkout`, `issue <description>` |
| `/feature` | Orchestrates analysis → GitHub issue → branch checkout → agent scaffolding for a new feature. Also: `push` creates the PR, `merge checkout` merges and returns to default |
| `/project` | Project-level Claude configuration: `init` scaffolds `.claude/`, `config` invokes `project-conf-agent` |

---

## `/feature` — multi-agent workflow

`/feature <idea>` orchestrates the user, `analyst-agent`, `gh-agent`, and `project-conf-agent` to go from a rough idea to a ready-to-work branch with scaffolded feature agents.

**Agents involved:**

| Agent | Role | Model |
|-------|------|-------|
| `analyst-agent` | Researches the codebase and web, asks clarifying questions, proposes and iterates on the feature description until the user confirms | Opus |
| `gh-agent` | Creates the GitHub issue, determines the default branch, creates and checks out a `feat/<n>-<slug>` branch | Sonnet |
| `project-conf-agent` | Inspects the project stack, assesses complexity, and scaffolds or reassesses feature-specific agents in `.claude/` | Sonnet |

> **Note — repo targeting is automatic.** `gh-agent` uses the `gh` CLI, which reads the `origin` remote of whichever git repository Claude is running in. You do not need to configure a target repo anywhere — opening Claude Code inside a project is sufficient for all issue and PR operations to target the correct GitHub repo.

**Workflows:**

```
/feature propose <title>                     (lightweight — no analysis, no checkout)
User                     /feature                              gh-agent
 │                           │                                    │
 │  propose <title>          │                                    │
 │──────────────────────────>│                                    │
 │<─── draft ────────────────│                                    │
 │  iterate / approve        │                                    │
 │──────────────────────────>│                                    │
 │                           │  invoke(description, checkout=false)│
 │                           │───────────────────────────────────>│
 │                           │                                    │ gh issue create
 │                           │                                    │ git branch + push
 │<── issue URL + branch ─────────────────────────────────────────│


/feature <idea>                              (full flow)
User         /feature      analyst-agent        gh-agent      project-conf-agent
 │               │                │                 │                  │
 │  /feature     │                │                 │                  │
 │──────────────>│  invoke(idea)  │                 │                  │
 │               │───────────────>│                 │                  │
 │<──── questions / clarifications ─────────────────│                  │
 │───── answers ───────────────────────────────────>│                  │
 │<──── proposed description ───────────────────────│                  │
 │  confirm      │                │                 │                  │
 │───────────────────────────────>│                 │                  │
 │               │<─ approved ────│                 │                  │
 │               │  invoke(description, checkout=true)                 │
 │               │─────────────────────────────────>│                  │
 │               │                                  │ gh issue create  │
 │               │                                  │ git checkout -b  │
 │<──────────────────────── issue URL + branch ─────│                  │
 │               │  invoke(scaffold agents)         │                  │
 │               │────────────────────────────────────────────────────>│
 │<──────────────────────── feature work ──────────────────────────────│
 


/feature push                                (create PR when work is done)
User         /feature          gh-agent
 │               │                 │
 │  push         │                 │
 │──────────────>│  invoke(merge)  │
 │               │────────────────>│
 │               │                 │ git log (commits vs default)
 │               │                 │ gh issue list (open issues)
 │               │                 │ [analyse coverage]
 │<── matches + proposed issues ───│
 │  confirm / correct              │
 │────────────────────────────────>│
 │               │                 │ gh issue create (new issues)
 │               │                 │ gh pr create --body "Closes #..."
 │<── PR URL ──────────────────────│


/feature merge checkout                      (merge after testing locally)
User         /feature              gh-agent
 │               │                     │
 │  merge        │                     │
 │  checkout     │                     │
 │──────────────>│  invoke(merge       │
 │               │  approve checkout)  │
 │               │────────────────────>│
 │               │                     │ gh pr merge
 │               │                     │ git checkout <default>
 │               │                     │ git pull
 │               │                     │ git branch -d <feature>
 │<─ done ─────────────────────────────│
```

---

## `CLAUDE.md`

`CLAUDE.md` is a plain Markdown file placed at the project root. Claude Code reads it automatically at the start of every session in that project. It is the mechanism for giving Claude persistent project context without relying on conversation history.

Without `CLAUDE.md`, Claude has no memory of your stack, conventions, or validation commands between sessions. With it, every session starts with a complete picture of the project.

**What to put in it:**

```markdown
# Project: My App

## Overview
What the project does in 2-3 sentences.

## Tech Stack
- Frontend: Next.js 14, TypeScript, Tailwind
- Backend: FastAPI, PostgreSQL
- Testing: Vitest, pytest
- Lint/Format: Biome, Ruff

## Validation Commands
lint:      npx biome check .
typecheck: npx tsc --noEmit
test:      npm run test
build:     npm run build

## Project Structure
src/
├── components/
├── features/
└── lib/

## Coding Standards
- All public functions must have tests (TDD)
- No `any` types in TypeScript
- Max 40 lines per function

## Definition of Done
- [ ] Tests written and passing
- [ ] Linter passes
- [ ] No console.log in production code
```
