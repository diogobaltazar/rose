# rose

Installs and manages Claude Code configuration.

## Prerequisites

- **GitHub CLI** authenticated: `gh auth login` — rose uses `gh` (not SSH keys) for all GitHub operations (issue creation, branch management, token injection into Docker). Run this once per host before using rose.

## Setup

Add this alias to your `~/.zshrc`:

```bash
alias rose='mkdir -p "$HOME/.claude" && docker run --rm -it \
  -v "$(pwd):/project" \
  -v "$HOME/.claude:/claude" \
  -v "$HOME/.ssh:/root/.ssh:ro" \
  -e GITHUB_TOKEN="$(gh auth token 2>/dev/null)" \
  rose:latest'
```

Then reload:
```bash
source ~/.zshrc
```

### Developer setup

If you're working on rose itself, set `ROSE_DEV` to the repo path. The alias will then use `docker compose` (which rebuilds on source changes) instead of the published image:

```bash
export ROSE_DEV="$HOME/source/rose"
alias rose='mkdir -p "$HOME/.claude" && \
  if [ -n "${ROSE_DEV:-}" ]; then \
    GITHUB_TOKEN="$(gh auth token 2>/dev/null)" TARGET_PROJECT="$(pwd)" \
      docker compose -f "$ROSE_DEV/compose.yml" run --rm rose; \
  else \
    docker run --rm -it \
      -v "$(pwd):/project" \
      -v "$HOME/.claude:/claude" \
      -v "$HOME/.ssh:/root/.ssh:ro" \
      -e GITHUB_TOKEN="$(gh auth token 2>/dev/null)" \
      rose:latest; \
  fi'
```

Unset `ROSE_DEV` (or don't set it) to use the published image like a regular client.

## Commands

| Command | Does |
|---|---|
| `rose install` | Install global Claude config onto host (`~/.claude`) |
| `rose reinstall` | Wipe `~/.claude` and reinstall from scratch |
| `rose remove` | Remove rose Claude setup from current project |
| `rose uninstall` | Remove rose config from `~/.claude` |

### rose install

Run once per host. Installs to `~/.claude`:

```
~/.claude/
├── CLAUDE.md                       # global persona and tone
├── settings.json                   # env vars + lifecycle hooks
├── hooks/
│   └── post-write-validate.sh      # lints every file after Write/Edit
├── agents/
│   ├── git-agent.md                # commit and push operations
│   ├── analyst-agent.md            # feature analysis and scoping
│   └── gh-agent.md                 # GitHub issue + branch creation
└── commands/
    ├── git.md                      # /git commit, /git push, /git commit push
    ├── feature.md                  # /feature
    ├── issue.md                    # /issue
    └── commit.md                   # /commit
```

```bash
rose install                # install into ~/.claude
rose install --force        # overwrite existing files
rose install --reset        # wipe ~/.claude and reinstall from scratch
rose reinstall              # alias for rose install --reset
```

### rose remove

Removes `.claude/agents/` and `CLAUDE.md` from the current project.

```bash
rose remove      # prompts for confirmation
rose remove -y   # skip confirmation
```

### rose uninstall

Removes rose's global config from `~/.claude`.

```bash
rose uninstall      # prompts for confirmation
rose uninstall -y   # skip confirmation
```

## This repo IS the config

The `global/` directory is the source of truth. All definitions flow via `rose install`:

```
global/  →  rose install  →  ~/.claude/
```

Never edit `~/.claude` directly — changes are overwritten on the next `rose reinstall`.

## Build

```bash
docker build -t rose .
```

---

## Claude Code agent setup — complete reference

This section explains every file and concept behind the `.claude/` configuration tree. Rose is built on top of these primitives. Understanding them lets you extend or replace any part of the setup.

### Two config scopes

Claude Code has two distinct config locations that layer on top of each other:

| Scope | Location | Loaded |
|-------|----------|--------|
| **Global** | `~/.claude/` | Every Claude Code session on this machine |
| **Project** | `<project>/.claude/` | Only when Claude is opened inside that project directory |

Global config sets up the agent's baseline behaviours (hooks, global agents, slash commands). Project config adds project-specific context on top (component agents, `CLAUDE.md`).

---

### `~/.claude/` — global config tree

```
~/.claude/
├── CLAUDE.md              # Global persona and tone (read every session)
├── settings.json          # Core configuration: env vars, hooks
├── hooks/
│   └── post-write-validate.sh   # Shell script run after every file write
├── agents/                # Global subagents available in every session
│   ├── git-agent.md
│   ├── analyst-agent.md
│   └── gh-agent.md
└── commands/              # Slash commands available in every session
    ├── git.md
    ├── feature.md
    ├── issue.md
    └── commit.md
```

---

### `settings.json`

The main config file. Supports two top-level keys: `env` and `hooks`.

```json
{
  "env": { ... },
  "hooks": { ... }
}
```

#### `env`

Key-value pairs injected as environment variables into every Claude Code session. Use this for API base URLs, auth tokens, and custom HTTP headers — anything that varies per machine or user but shouldn't live in code.

```json
"env": {
  "ANTHROPIC_BASE_URL": "http://localhost:8080",
  "ANTHROPIC_AUTH_TOKEN": "dummy-gateway-token",
  "ANTHROPIC_CUSTOM_HEADERS": "x-portkey-metadata: {...}"
}
```

#### `hooks`

Hooks let you attach shell commands or prompt injections to lifecycle events in the Claude Code session. There are four hook events:

| Event | When it fires |
|-------|---------------|
| `PreToolUse` | Before Claude calls any tool |
| `PostToolUse` | After Claude calls any tool |
| `Stop` | When Claude is about to stop and return control to the user |
| `SubagentStop` | When a subagent (spawned via the Agent tool) is about to stop |

Each hook entry has a `matcher` (regex matched against the tool name, for tool-related events) and a list of hook definitions:

```json
"PostToolUse": [
  {
    "matcher": "Write|Edit",
    "hooks": [
      {
        "type": "command",
        "command": "bash ~/.claude/hooks/post-write-validate.sh",
        "timeout": 30
      }
    ]
  }
]
```

**Hook types:**

- `"type": "command"` — runs a shell command. The hook receives a JSON payload on stdin describing the event (tool name, input, output). Exit code controls behaviour:
  - `0` — pass silently
  - `2` — feed the hook's stderr back to Claude as an error to fix
  - Any other non-zero — block the action and surface the error

- `"type": "prompt"` — injects a prompt string into Claude's context at that lifecycle point. Used on `Stop` and `SubagentStop` to enforce checklists before Claude finishes.

---

### `hooks/post-write-validate.sh`

A `PostToolUse` hook that fires after every `Write` or `Edit` tool call. It:

1. Reads the JSON event from stdin and extracts `tool_input.file_path`
2. Detects the file extension
3. Runs the appropriate linter for that file type:
   - `.ts/.tsx/.js/.jsx` → Biome (if `biome.json` exists) or ESLint
   - `.py` → Ruff
   - `.rs` → rustfmt
   - `.go` → gofmt
4. Exits `2` if there are errors, feeding them back to Claude to fix immediately

This creates a tight feedback loop: Claude writes a file, it is linted instantly, and any errors are returned before Claude moves on to the next step.

---

### Agents

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
| `gh-agent` | Creates GitHub issues, manages branches |

---

### Commands (slash commands)

Slash commands are user-invocable shortcuts. Typing `/commit` in a Claude Code session triggers the corresponding command file.

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
| `/feature` | Orchestrates analysis → GitHub issue → branch checkout for a new feature |
| `/issue` | Drafts and creates a GitHub issue, then branches and checks out |

---

### `/feature` — multi-agent workflow

`/feature <idea>` orchestrates three participants — the user, `analyst-agent`, and `gh-agent` — to go from a rough idea to a ready-to-work branch.

**Agents involved:**

| Agent | Role | Model |
|-------|------|-------|
| `analyst-agent` | Researches the codebase and web, asks clarifying questions, proposes and iterates on the feature description until the user confirms | Opus |
| `gh-agent` | Creates the GitHub issue, determines the default branch, creates and checks out a `feat/<n>-<slug>` branch | Sonnet |

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
User                /feature          analyst-agent              gh-agent
 │                      │                   │                       │
 │  /feature <idea>     │                   │                       │
 │─────────────────────>│  invoke(idea)     │                       │
 │                      │──────────────────>│ read CLAUDE.md,       │
 │                      │                   │ explore, research web  │
 │<──────── questions / clarifications ─────│                       │
 │─────────── answers ─────────────────────>│                       │
 │<──────── proposed description ───────────│                       │
 │  confirm             │                   │                       │
 │─────────────────────────────────────────>│                       │
 │                      │<─ approved ───────│                       │
 │                      │  invoke(description, checkout=true)       │
 │                      │──────────────────────────────────────────>│
 │                      │                   │  gh issue create      │
 │                      │                   │  git checkout -b      │
 │<──────────────── issue URL + branch ──────────────────────────────│


/gh merge                                    (after work is done)
User         /gh               gh-agent
 │            │                    │
 │  merge     │                    │
 │───────────>│                    │
 │            │  invoke(merge)     │
 │            │───────────────────>│
 │            │                    │ gh pr create --base <default>
 │<── PR URL ──────────────────────│


/gh merge approve checkout                   (admin — merge and return to default)
User         /gh               gh-agent
 │            │                    │
 │  merge     │                    │
 │  approve   │                    │
 │  checkout  │                    │
 │───────────>│  invoke(merge      │
 │            │  approve checkout) │
 │            │───────────────────>│
 │            │                    │ gh pr merge
 │            │                    │ git checkout <default>
 │            │                    │ git pull
 │<─ done ─────────────────────────│
```

---

### `CLAUDE.md`

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

The `Validation Commands` block is especially important: the `Stop` hook's prompt instructs Claude to run these commands before finishing any task. If they fail, Claude continues working until they pass.
