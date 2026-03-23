# rose

Installs and manages Claude Code configuration.

## Prerequisites

**GitHub CLI** authenticated: `gh auth login` — rose uses `gh` for all GitHub operations. Run this once per host.

## Setup

Add this function to your `~/.zshrc`:

```bash
rose() {
  docker run --rm -it \
    -v "$(pwd):/project" \
    -v "$HOME/.claude:/claude" \
    -v "$HOME/.ssh:/root/.ssh:ro" \
    -e GITHUB_TOKEN="$(gh auth token 2>/dev/null)" \
    rose:latest "$@"
}
```

Then reload:

```bash
source ~/.zshrc
```

### Developer setup

If you're working on rose itself, set `ROSE_DEV` to the repo path. The function will use `docker compose` (which rebuilds on source changes) instead of the published image:

```bash
export ROSE_DEV="$HOME/rose"

rose() {
  local cmd="${1:-help}"
  if [[ -n "${ROSE_DEV:-}" ]]; then
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
}
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
rose install          # install into ~/.claude
rose install --force  # overwrite existing files
rose reinstall        # wipe ~/.claude and reinstall from scratch
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
