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
  local hash_file="${XDG_CACHE_HOME:-$HOME/.cache}/rose/build_hash"
  local current_hash
  current_hash=$(find "$ROSE_DEV" \
    \( -name "*.py" -o -name "*.md" -o -name "*.json" -o -name "*.sh" -o -name "Dockerfile" -o -name "requirements.txt" \) \
    -not -path "*/.git/*" \
    | sort | xargs shasum -a 256 2>/dev/null | shasum -a 256 | cut -d' ' -f1)

  if [[ "$(cat "$hash_file" 2>/dev/null)" != "$current_hash" ]]; then
    docker compose -f "$ROSE_DEV/compose.yml" build rose > /dev/null 2>&1
    mkdir -p "$(dirname "$hash_file")"
    echo "$current_hash" > "$hash_file"
  fi
}

rose() {
  local cmd="${1:-help}"

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

    if [[ -n "${ROSE_DEV:-}" ]]; then
      _rose_build_if_changed
      TARGET_PROJECT="$(pwd)" GITHUB_TOKEN="$(gh auth token 2>/dev/null)" \
        docker compose --progress quiet -f "$ROSE_DEV/compose.yml" run --rm rose install "${extra_args[@]}"
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

  elif [[ "$cmd" == "config" ]]; then
    local domain="${2:-}" op="${3:-}" arg="${4:-}"
    local config_file="$HOME/.config/rose/config.json"
    mkdir -p "$(dirname "$config_file")"
    case "$domain/$op" in
      observe/add)
        local path; path=$(python3 -c "import os; print(os.path.realpath('${arg/#\~/$HOME}'))")
        python3 -c "
import json; f='${config_file}'
try: d=json.load(open(f))
except: d={}
ps=d.setdefault('projects',[])
if '${path}' not in ps: ps.append('${path}'); json.dump(d,open(f,'w'),indent=2); print('Added: ${path}')
else: print('Already registered: ${path}')
"     ;;
      observe/remove)
        local path; path=$(python3 -c "import os; print(os.path.realpath('${arg/#\~/$HOME}'))")
        python3 -c "
import json; f='${config_file}'
try: d=json.load(open(f))
except: d={}
ps=d.get('projects',[])
if '${path}' in ps: ps.remove('${path}'); d['projects']=ps; json.dump(d,open(f,'w'),indent=2); print('Removed: ${path}')
else: print('Not registered: ${path}')
"     ;;
      observe/list)
        python3 -c "
import json; f='${config_file}'
try: ps=json.load(open(f)).get('projects',[])
except: ps=[]
print('\n'.join(ps) if ps else 'No projects registered. Use: rose config observe add <path>')
"     ;;
      *) echo "Usage: rose config observe <add|remove|list> [path]" ;;
    esac

  elif [[ "$cmd" == "observe" ]]; then
    local subcmd="${2:-}"
    local dev_dir
    # Auto-detect: prefer cwd if it looks like a rose source tree
    if [[ -f "$(pwd)/compose.yml" && -d "$(pwd)/src/rose" ]]; then
      dev_dir="$(pwd)"
    else
      dev_dir="${ROSE_DEV:-}"
    fi
    local compose_file="${dev_dir:+$dev_dir/}compose.yml"
    case "$subcmd" in
      start)
        mkdir -p "$HOME/.claude/logs" "$HOME/.config/rose"
        echo "Starting rose observe at http://localhost:5100 ..."
        docker compose -f "$compose_file" up --build --detach api web
        ;;
      stop)
        docker compose -f "$compose_file" stop api web
        ;;
      restart)
        docker compose -f "$compose_file" restart api web
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
    if [[ -n "${ROSE_DEV:-}" ]]; then
      _rose_build_if_changed
      TARGET_PROJECT="$(pwd)" GITHUB_TOKEN="$(gh auth token 2>/dev/null)" \
        docker compose --progress quiet -f "$ROSE_DEV/compose.yml" run --rm rose "$cmd" "${@:2}"
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
