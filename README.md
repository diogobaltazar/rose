# rose

Installs and manages Claude Code configuration.

## Prerequisites

**GitHub CLI** authenticated: `gh auth login` — rose uses `gh` for all GitHub operations. Run this once per host.

## Setup

Add the following to your `~/.zshrc` and reload with `source ~/.zshrc`:

```bash
# Set ROSE_DEV to your rose source path to build from source on every run.
export ROSE_DEV="$HOME/rose"

_rose_build_if_changed() {
  local dev_dir="$1"
  local hash_file="${XDG_CACHE_HOME:-$HOME/.cache}/rose/build_hash"
  local current_hash
  current_hash=$(find "$dev_dir" \
    \( -name "*.py" -o -name "*.md" -o -name "*.json" -o -name "*.sh" -o -name "Dockerfile" -o -name "requirements.txt" \) \
    -not -path "*/.git/*" \
    | sort | xargs shasum -a 256 2>/dev/null | shasum -a 256 | cut -d' ' -f1)

  if [[ "$(cat "$hash_file" 2>/dev/null)" != "$current_hash" ]]; then
    docker compose -f "$dev_dir/compose.yml" build rose > /dev/null 2>&1
    mkdir -p "$(dirname "$hash_file")"
    echo "$current_hash" > "$hash_file"
  fi
}

rose() {
  local cmd="${1:-help}"

  # Auto-detect: prefer cwd if it looks like a rose source tree (worktree support).
  local _rose_dev
  if [[ -f "$(pwd)/compose.yml" && -d "$(pwd)/src/rose" ]]; then
    _rose_dev="$(pwd)"
  else
    _rose_dev="${ROSE_DEV:-}"
  fi

  if [[ "$cmd" == "install" || "$cmd" == "reinstall" ]]; then
    shift
    local link_path=""
    local reset=false
    local extra_args=()
    while [[ $# -gt 0 ]]; do
      case "$1" in
        --link)  link_path="${2/#\~/$HOME}"; shift 2 ;;
        --reset) reset=true; shift ;;
        *)       extra_args+=("$1"); shift ;;
      esac
    done
    [[ "$cmd" == "reinstall" ]] && reset=true

    local mount_path="${link_path:-$HOME/.claude}"

    if [[ "$reset" == true ]]; then
      local real_path="$mount_path"
      [[ -L "$mount_path" ]] && real_path="$(readlink "$mount_path")"
      echo "Resetting ${real_path}..."
      rm -rf "${real_path:?}"
    fi

    mkdir -p "$mount_path"

    if [[ -n "$_rose_dev" ]]; then
      _rose_build_if_changed "$_rose_dev"
      TARGET_PROJECT="$(pwd)" GITHUB_TOKEN="$(gh auth token 2>/dev/null)" \
        docker compose --progress quiet -f "$_rose_dev/compose.yml" run --rm rose install "${extra_args[@]}"
    else
      docker run --rm -it \
        -v "$(pwd):/project" \
        -v "$mount_path:/claude" \
        -v "$HOME/.ssh:/root/.ssh:ro" \
        -e GITHUB_TOKEN="$(gh auth token 2>/dev/null)" \
        rose:latest install "${extra_args[@]}"
    fi

    if [[ -n "$link_path" ]]; then
      ln -sf "$link_path" "$HOME/.claude"
      echo "Symlink: ~/.claude -> $link_path"
    fi

  elif [[ "$cmd" == "observe" ]]; then
    local subcmd="${2:-}"
    local compose_file="${_rose_dev:+$_rose_dev/}compose.yml"
    case "$subcmd" in
      start)
        mkdir -p "$HOME/.claude/logs" "$HOME/.config/rose"
        echo "Starting rose observe at http://localhost:5100 ..."
        docker compose -p rose -f "$compose_file" up --build --detach api web
        ;;
      stop)
        docker compose -p rose -f "$compose_file" stop api web
        ;;
      restart)
        docker compose -p rose -f "$compose_file" restart api web
        ;;
      status)
        for name in rose-api rose-web; do
          if docker ps --filter "name=^${name}$" --filter "status=running" --format "{{.Names}}" | grep -q "^${name}$"; then
            printf "\033[32m●\033[0m %s running\n" "$name"
          else
            printf "\033[31m●\033[0m %s down\n" "$name"
          fi
        done
        ;;
      *)
        echo "Usage: rose observe <start|stop|restart|status>"
        ;;
    esac

  else
    if [[ -n "$_rose_dev" ]]; then
      _rose_build_if_changed "$_rose_dev"
      TARGET_PROJECT="$(pwd)" GITHUB_TOKEN="$(gh auth token 2>/dev/null)" \
        docker compose --progress quiet -f "$_rose_dev/compose.yml" run --rm rose "$cmd" "${@:2}"
    else
      docker run --rm -it \
        -v "$(pwd):/project" \
        -v "$HOME/.claude:/claude" \
        -v "$HOME/.ssh:/root/.ssh:ro" \
        -e GITHUB_TOKEN="$(gh auth token 2>/dev/null)" \
        rose:latest "$cmd" "${@:2}"
    fi
  fi
}
```

The function auto-detects rose source trees: if the current directory contains `compose.yml` and `src/rose/`, it uses that directory — no need to update `ROSE_DEV` when switching between the main repo and worktrees.

Unset `ROSE_DEV` (or don't set it) to use the published image.

## Commands

| Command | Does |
|---|---|
| `rose install` | Install global Claude config onto host (`~/.claude`) |
| `rose reinstall` | Wipe `~/.claude` and reinstall from scratch |
| `rose uninstall` | Remove rose config from `~/.claude` |
| `rose observe start` | Start the live session dashboard at `http://localhost:5100` (detached) |
| `rose observe stop` | Stop the dashboard containers |
| `rose observe restart` | Restart the dashboard containers |
| `rose observe status` | Show running (green) / down (red) status for each container |
| `rose config observe add <path>` | Register a project for the dashboard to monitor |
| `rose config observe remove <path>` | Deregister a project |
| `rose config observe list` | List registered projects |

### rose install

Run once per host. Installs to `~/.claude`:

```
~/.claude/
├── CLAUDE.md        # global persona and tone
├── settings.json    # env vars + lifecycle hooks
├── hooks/
│   ├── log-session-start.sh   # writes meta.json + session.start event
│   ├── log-tool-event.sh      # appends tool.call events (PostToolUse)
│   └── log-session-end.sh     # derives outcome + session.end (Stop)
├── agents/
│   ├── analyst.md   # R1–R5, W1, decision gate
│   ├── engineer.md  # D3–D4
│   ├── github.md    # D1, D6, D7, P2
│   └── git.md       # D5
└── commands/
    ├── feature.md   # /feature — full lifecycle orchestrator
    ├── github.md    # /github
    ├── git.md       # /git
    └── project.md   # /project
```

```bash
rose install          # install into ~/.claude
rose install --force  # overwrite existing files
rose reinstall        # wipe ~/.claude and reinstall from scratch
```

### rose observe

`rose observe` is handled by the shell function — it runs `docker compose` directly on the host (Docker is not available inside the rose container).

```bash
rose observe start    # build and start rose-api + rose-web, detached
rose observe stop     # stop containers
rose observe restart  # restart containers
rose observe status   # green ● running / red ● down per container
```

The dashboard runs at **http://localhost:5100**. It watches `~/.claude/logs/` for active Claude sessions and renders the lifecycle state machine with the current step highlighted.

Register projects to observe (see [rose config](#rose-config)):

```bash
rose config observe add ~/source/my-project
```

### rose config

A CLI command that runs inside the rose container. Config is stored at `~/.config/rose/config.json` (mounted read-write into the container).

```bash
rose config observe add ~/source/my-project     # register a project
rose config observe remove ~/source/my-project  # deregister
rose config observe list                        # print registered projects
```

Paths are resolved to absolute form. `rose observe` will filter sessions to registered projects only; if no projects are registered it shows all active sessions.

### rose uninstall

Removes rose's global config from `~/.claude`.

```bash
rose uninstall      # prompts for confirmation
rose uninstall -y   # skip confirmation
```

## Feature Lifecycle

Rose implements a structured engineering workflow as a state machine. Every unit of work — feature, bug fix, dependency upgrade, or investigation — passes through the same pipeline.

```mermaid
stateDiagram-v2
    direction TB

    state "Entry Points" as entry {
        E1: E1 — Feature idea
        E2: E2 — Bug report
        E3: E3 — Dependency upgrade
        E4: E4 — Spike / investigation
        E5: E5 — Autonomous pickup [future]
    }

    state "Requirements Pipeline" as pipeline {
        R1: R1 — Clarify intent
        R2: R2 — Requirements & acceptance criteria
        R3: R3 — Issue matching
        R4: R4 — Technical feasibility
        R5: R5 — Spec reconciliation

        R1 --> R2: user confirms intent
        R1 --> R1: analyst asks follow-up
        R2 --> R2: analyst refines criteria
        R2 --> R3: user confirms requirements
        R3 --> R3: analyst suggests overlaps
        R3 --> R4: user validates issue mapping
        R4 --> R2: feasibility concern revises requirements
        R4 --> R5: feasible, proceed
        R5 --> R5: conflict — user resolves
    }

    state decision <<choice>>

    state "Investigation" as investigation {
        W1: W1 — Write-up
    }

    state "Delivery Pipeline" as delivery {
        D1: D1 — Issue creation
        D2: D2 — Worktree setup
        D3: D3 — Implementation
        D4: D4 — Verification
        D5: D5 — Commit sorting
        D6: D6 — PR creation / update
        D7: D7 — Adjacent work detection
        P2: P2 — Merge PR

        D1 --> D2
        D2 --> D3
        D3 --> D4
        D4 --> D3: implementation failure
        D4 --> D5: verification passes
        D5 --> D6
        D6 --> D7
        D7 --> D1: separate unit — new issue
        D7 --> P2: PR ready
    }

    S1: S1 — Stakeholder input [interrupt]
    V1: V1 — State visualisation [future]

    E1 --> R1
    E2 --> R1
    E3 --> R1
    E4 --> R1
    E5 --> R1

    R5 --> decision
    decision --> W1: investigation
    decision --> D1: delivery
    W1 --> [*]: write-up complete

    D4 --> R2: requirement failure
    P2 --> [*]: PR merged, issues closed

    S1 --> R1
    S1 --> R2
    S1 --> R3
    S1 --> R4
    S1 --> R5
    S1 --> D1
    S1 --> D3
    S1 --> D6
```

See [CLAUDE.md](CLAUDE.md) for the full process specification with actors, triggers, inputs, outputs, and exit conditions for each step.

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

For a full explanation of Claude Code's configuration primitives — settings.json, hooks, agents, slash commands, CLAUDE.md — see [docs/reference.md](docs/reference.md).

---

## Claude Setup

Design decisions made to the Claude Code configuration that lives in `global/` and is installed to `~/.claude/`.

### Architecture overview

The setup is built around three Claude Code primitives:

| Primitive | What it is | Where |
|-----------|-----------|-------|
| **Command** | A slash command (`/feature`) that runs in the main session as Rose | `global/commands/feature.md` |
| **Agent** | A specialist subagent spawned by the command | `global/agents/` |
| **Hook** | A shell script fired at lifecycle events | `global/hooks/` |

### Agent teams — parallel research phase

The `/feature` command orchestrates a parallel research phase before any implementation work begins. Three specialist agents run simultaneously:

| Agent | Model | Purpose |
|-------|-------|---------|
| `deep-research` | claude-sonnet-4-6 | External knowledge — technology patterns, prior art, business context |
| `code-inspect` | claude-sonnet-4-6 | Codebase knowledge — architecture, conventions, entry points, constraints |
| `backlog-inspect` | claude-haiku-4-5-20251001 | GitHub backlog — duplicates, related issues, blockers |

**Why teammate mode, not subagents**

The original design used `Agent` tool calls with `run_in_background: true`. This launches agents asynchronously but the orchestrator still blocks — it cannot return to the user until all three resolve. Teammate mode (enabled via `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`) uses `TeamCreate` + named teammates, which allows the lead to return to the user immediately and collect results across turns via `SendMessage`.

**Why these three agents**

- `deep-research` and `backlog-inspect` access external systems (Gemini/web, GitHub) — genuine I/O parallelism worth the overhead.
- `code-inspect` reads the local codebase. It was kept as a teammate because in the fire-and-return model the lead cannot do the reading itself before returning to the user. If the design reverts to blocking, `code-inspect` is the first candidate to fold back into the main session.

**Model selection rationale**

- `claude-opus-4-6` for the orchestrator (Rose): synthesis across multiple research streams requires the strongest reasoning.
- `claude-sonnet-4-6` for research agents: capable web search and code reading, faster and cheaper than Opus.
- `claude-haiku-4-5-20251001` for backlog-inspect: purely JSON parsing and pattern matching against GitHub issue data — no reasoning depth needed.

### Deep research — Gemini relay pattern

`deep-research` does not call `WebSearch` directly. Instead:

1. It analyses what external knowledge the feature actually requires.
2. It formulates 1–3 targeted prompts and asks the user to run them in **Gemini Deep Research**.
3. The lead relays the queries to the user; the user pastes results back; the lead relays results to the agent.
4. The agent synthesises Gemini output with codebase context and reports to the lead.

**Why**: Gemini Deep Research uses Google's own search index and runs a genuine multi-step iterative research loop. `WebSearch` via Brave cannot match it for breadth or depth. The man-in-the-middle relay keeps the agent in the loop without requiring API access to Gemini Deep Research (which is a product feature, not an exposed endpoint).

If no external knowledge is genuinely needed, the agent skips to synthesis immediately.

### Hook design

Hooks capture lifecycle events without requiring agents to emit logging themselves.

| Hook | Event | Does |
|------|-------|------|
| `log-session-start.sh` | `PreToolUse` (fires once via sentinel) | Creates log dir, writes `meta.json`, emits `session.start` |
| `log-session-end.sh` | `Stop` | Derives outcome from last `step.exit`, emits `session.end`, updates `meta.json` |
| `log-subagent-start.sh` | `SubagentStart` | Maps agent type → step code, emits `step.enter` |
| `log-subagent-stop.sh` | `SubagentStop` | Maps agent type → step code, emits `step.exit` |

**Why hooks for step logging, not agent-side bash**: hooks fire reliably regardless of what the agent does. If step logging were written into each agent's prompt, an agent that crashes or returns early would miss the exit event. The hook fires at the OS process boundary.

`PostToolUse` / `log-tool-event.sh` was removed — it generated tool-call events that no downstream consumer used, adding noise with no benefit.

### Status line

A `statusline.sh` script provides a live progress bar at the bottom of every Claude Code session:

```
█████████░░░░░░░░░░░  45%   Claude Sonnet 4.6   12.4k / 200k tokens
```

Colour transitions: green → yellow (60%) → red (85%).

The script lives at `~/.claude/statusline.sh` directly (not inside `global/`) and is wired into `settings.json`. If you run `rose reinstall`, the settings entry is preserved but the script must be recreated manually — or moved into `global/` to be managed by rose.

### Teammate mode display

`"teammateMode": "in-process"` is set in `~/.claude.json`. This renders all teammates in the main terminal rather than spawning tmux panes. Use `Shift+Up/Down` to switch between agents, `Enter` to view.

Tmux mode was not chosen because the setup runs over an SSH/ONA connection where tmux pane lifecycle is less reliable.
