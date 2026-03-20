# rose

Coding agent scaffolding tool. Bootstraps Claude Code super-agent config into any project.

## Setup

Add this alias to your `~/.zshrc`:

```bash
alias rose='docker run --rm -it \
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

## Commands

| Command | Does |
|---|---|
| `rose install` | Install global Claude config onto host (`~/.claude`) |
| `rose reinstall` | Wipe `~/.claude` and reinstall from scratch (alias for `rose install --reset`) |
| `rose init` | Bootstrap current project with `CLAUDE.md` + component agents |
| `rose remove` | Remove rose Claude setup from current project |
| `rose add <name>` | Add a registry config to current project |
| `rose register <path>` | Register a project agent into the rose registry via PR |

### rose install
Run once per host. Installs to `~/.claude`:
- `settings.json` — hooks (feedback loops, auto-linting, stop checks)
- `hooks/` — post-write validation script
- `agents/` — global agents (commit-organizer, doc-verifier, code-health, tdd-enforcer)
- `commands/` — slash commands (/commit, /verify, /docs, /health)

```bash
rose install                          # install into ~/.claude
rose install --force                  # overwrite existing files
rose install --reset                  # wipe ~/.claude and reinstall from scratch
rose install --link ~/source/.claude  # install into ~/source/.claude and symlink ~/.claude to it
rose reinstall                        # alias for rose install --reset
```

### rose init
Run once per project. Copies into current directory:
- `CLAUDE.md` — fill in your stack and validation commands
- `.claude/agents/` — component agents (auth, list-ui, rag)

```bash
rose init
```

### rose remove
Removes `.claude/agents/` and `CLAUDE.md` from the current project.

```bash
rose remove      # prompts for confirmation
rose remove -y   # skip confirmation
```

### rose add
Import a named config from the registry into the current project.

```bash
rose add fastapi
rose add rag-milvus
rose add fastapi --force   # overwrite existing agent
```

### rose register
Register a project agent into the rose registry by opening a PR.

```bash
rose register .claude/agents/rag.md
rose register .claude/agents/rag.md --name rag-milvus
```

## Registry

Built-in configs shipped with the image:

| Name | Description |
|---|---|
| `fastapi` | FastAPI service agent |
| `rag-milvus` | RAG pipeline with Milvus vector store |

## This repo IS the config

All files under `.claude/` are the source of truth:
- `.claude/template/` — copied by `rose init`
- `.claude/global/` — installed by `rose install`
- `.claude/registry/` — imported by `rose add`

To update config, edit files here and rebuild the image.

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

Rose installs global config via `rose install` and project config via `rose init`.

---

### `~/.claude/` — global config tree

```
~/.claude/
├── settings.json          # Core configuration: env vars, hooks
├── hooks/
│   └── post-write-validate.sh   # Shell script run after every file write
├── agents/                # Global subagents available in every session
│   ├── commit-organizer.md
│   ├── doc-verifier.md
│   ├── code-health.md
│   └── tdd-enforcer.md
└── commands/              # Slash commands available in every session
    ├── commit.md
    ├── verify.md
    ├── docs.md
    └── health.md
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

| Agent | Description | Tools |
|-------|-------------|-------|
| `commit-organizer` | Audits changes, groups by concern, writes Conventional Commit messages, commits after approval | Bash, Read, Glob, Grep |
| `doc-verifier` | Checks docs match implementation; updates outdated docs in place | Read, Write, Edit, Glob, Grep, Bash |
| `code-health` | Audits for dead code, duplication, and tech debt; produces a prioritised report without making changes | Read, Glob, Grep, Bash |
| `tdd-enforcer` | Enforces RED → GREEN → REFACTOR cycle; writes failing test first, then minimal implementation | Read, Write, Edit, Bash, Glob, Grep |

**Rose's project template agents** (copied by `rose init`, one per component):

| Agent | Scope |
|-------|-------|
| `auth` | Login flows, sessions, JWT/OAuth, RBAC/ABAC, security hardening |
| `list-ui` | List components, pagination, filtering, sorting |
| `rag` | Retrieval-augmented generation, embeddings, vector store queries |

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

**`$ARGUMENTS`** is replaced with everything the user typed after the command name. For example, `/health src/auth` sets `$ARGUMENTS` to `src/auth`.

**Command placement:**

- `~/.claude/commands/` — global commands, available in every session
- `<project>/.claude/commands/` — project-scoped commands

**Rose's global commands:**

| Command | What it does |
|---------|-------------|
| `/commit` | Invokes `commit-organizer` agent to audit, group, and commit changes |
| `/verify` | Runs lint → typecheck → tests → doc check; fixes failures before reporting |
| `/docs` | Invokes `doc-verifier` agent to sync docs with implementation |
| `/health` | Invokes `code-health` agent to produce a prioritised audit report |

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

## Component Ownership (Agents)
| Component | Agent | Scope |
|-----------|-------|-------|
| Auth      | auth  | Login, sessions, permissions |

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

---

### `<project>/.claude/` — project config tree

```
<project>/
├── CLAUDE.md              # Persistent project context (read every session)
└── .claude/
    └── agents/            # Component agents for this project
        ├── auth.md
        ├── list-ui.md
        └── rag.md
```

`rose init` copies this structure from the template. Edit `CLAUDE.md` to match your stack and delete or replace agent files to match your components.

---

### The registry

The registry is a collection of reusable agent configs for common technology components. `rose add <name>` copies a registry agent into the current project's `.claude/agents/`.

Registry agents live in `.claude/registry/<name>/agent.md` inside the rose image. `rose register` opens a PR to add a new agent to the registry.

Built-in registry agents:

| Name | Technology |
|------|-----------|
| `fastapi` | FastAPI routes, Pydantic models, dependency injection, async patterns |
| `rag-milvus` | RAG pipeline with Milvus vector store, embeddings, retrieval |

## Build

```bash
docker build -t rose .
```
