# rose

rose is a scaffolding tool that installs and manages Claude Code configuration. This repo IS the source of truth for that configuration.

## Critical rule: edit the source code, not ~/.claude

When working inside this repo, any changes to Claude definitions — agents, commands, personas, hooks, settings — must be made to the source files here, **not** to `~/.claude` directly.

All definitions flow via `rose install`:

```
rose source (global/)  →  rose install  →  ~/.claude/
```

If you edit `~/.claude` directly, the change will be lost the next time someone runs `rose install`. Always edit the source here; the user will apply it by running `rose reinstall`.

## Project layout

```
global/        # Installed to ~/.claude/ by `rose install`
├── CLAUDE.md
├── settings.json
├── hooks/
│   ├── log-session-start.sh  # writes meta.json + session.start event (PreToolUse, once)
│   ├── log-tool-event.sh     # appends tool.call event (PostToolUse)
│   └── log-session-end.sh    # derives outcome + appends session.end (Stop)
├── agents/
│   ├── analyst.md      # Product analyst — R1-R5, W1, decision gate
│   ├── engineer.md     # Implementation agent — D3-D4
│   ├── github.md       # GitHub operations — D1, D6, D7, P2
│   └── git.md          # Git operations — D5
└── commands/
    ├── feature.md      # /feature workflow — full lifecycle orchestrator
    ├── github.md       # /github skill
    ├── git.md          # /git skill
    └── project.md      # /project skill (init, spec update)
src/rose/cli/  # Typer entrypoint (package)
├── __init__.py     # app definition, command registration
├── install.py      # rose install
├── uninstall.py    # rose uninstall
└── observe.py      # rose observe
src/rose/api/  # FastAPI backend for observe dashboard
├── Dockerfile
├── requirements.txt
└── main.py
src/rose/web/  # nginx frontend for observe dashboard
├── Dockerfile
├── nginx.conf
├── index.html
├── app.js
└── style.css
pyproject.toml
Dockerfile
compose.yml    # rose + api + web services
```

## Feature Lifecycle — Process Specification

Every unit of work passes through a single pipeline regardless of entry point. The pipeline is not strictly sequential — stages loop, run concurrently, or are interrupted by stakeholder input (S1) at any time.

### Entry Points

| Code | Name | Actor | Trigger | Notes |
|------|------|-------|---------|-------|
| **E1** | Feature idea | User | `/feature <idea>` | Most common entry point |
| **E2** | Bug report | User | User reports unexpected behaviour | Identical pipeline to E1 from R1 onward |
| **E3** | Dependency upgrade | User | Upgrade request | R4 especially important for breaking changes |
| **E4** | Spike / investigation | User | Research without delivery commitment | Routes to W1 after R5, not D1 |
| **E5** | Autonomous pickup | Rose *(future)* | Rose identifies a ready issue | Requires trust boundaries and approval gates |

### Requirements Pipeline

**[R1] Clarify intent**
- **Actor:** Analyst agent
- **Trigger:** Intent statement from any entry point
- **Input:** Raw user description
- **Output:** Confirmed, unambiguous statement of intent
- **Exit conditions:** User explicitly confirms. Loops until confirmation.
- **Notes:** Analyst researches codebase and web before asking questions. No assumptions made.

**[R2] Requirements & acceptance criteria**
- **Actor:** Analyst agent
- **Trigger:** R1 confirmed; or feedback loop from R4 or D4
- **Input:** Confirmed intent; or revised constraints from R4/D4
- **Output:** Structured feature description with acceptance criteria
- **Exit conditions:** User confirms. Loops until confirmation.
- **Notes:** Canonical artefact flowing through the rest of the pipeline.

**[R3] Issue matching**
- **Actor:** Analyst agent
- **Trigger:** R2 confirmed
- **Input:** Confirmed requirements; open GitHub issues (via `gh issue list`)
- **Output:** Overlap report — duplicates, related issues, partial coverage — with reasons
- **Exit conditions:** User validates the overlap analysis
- **Notes:** May run concurrently with R4. User makes the final call on scope merging.

**[R4] Technical feasibility**
- **Actor:** Analyst agent (reads code, does not write it)
- **Trigger:** R2 confirmed (may run alongside R3)
- **Input:** Confirmed requirements; codebase state
- **Output:** Feasibility assessment — risks, blockers, approaches, or a recommendation to revise R2
- **Exit conditions:** (a) feasible → R5; or (b) infeasible → R2 with revised constraints
- **Notes:** Surfaces architectural concerns, performance implications, dependency risks.

**[R5] Spec reconciliation**
- **Actor:** Analyst agent
- **Trigger:** R4 passes
- **Input:** Confirmed requirements; product specifications in CLAUDE.md
- **Output:** Updated CLAUDE.md, or a conflict report requiring user resolution
- **Exit conditions:** CLAUDE.md is consistent with the incoming feature. Conflicts resolved.
- **Notes:** Never silently overwrites a conflicting spec — conflicts always surfaced.

### Decision Gate (after R5)

- **Investigation** → W1. Applies when entry point was E4, or when R4/R5 determined no deliverable is warranted.
- **Delivery** → D1. Applies for all work resulting in code, configuration, or documentation changes to be merged.

### Investigation Close-out

**[W1] Write-up**
- **Actor:** Analyst agent
- **Trigger:** Decision gate selects investigation path
- **Input:** All findings from R1–R5
- **Output:** Written summary of findings, conclusions, and recommendations
- **Exit conditions:** Write-up delivered. No issue or PR created. Pipeline terminates.
- **Notes:** May recommend future E1 work.

### Delivery Pipeline

**[D1] Issue creation**
- **Actor:** GitHub agent
- **Trigger:** Decision gate selects delivery path
- **Input:** Confirmed feature description and acceptance criteria (R2); issue overlap analysis (R3)
- **Output:** GitHub issue (URL and number); remote branch (`feat/<n>-<slug>`)
- **Exit conditions:** Issue and branch exist on GitHub. No local checkout.

**[D2] Worktree setup**
- **Actor:** Feature command (orchestrator)
- **Trigger:** D1 complete
- **Input:** Branch name from D1
- **Output:** Active worktree session; branch tracking remote
- **Exit conditions:** Session is inside the worktree
- **Notes:** Uses `EnterWorktree`. Execution environment is always Docker.

**[D3] Implementation**
- **Actor:** Engineer agent
- **Trigger:** D2 complete; or loop-back from D4
- **Input:** Reconciled specification (R5); codebase context
- **Output:** Code changes satisfying acceptance criteria
- **Exit conditions:** Engineer has verified changes against acceptance criteria
- **Notes:** Minimum viable change only. Reads CLAUDE.md for conventions. No speculative refactoring.

**[D4] Verification**
- **Actor:** Engineer agent
- **Trigger:** D3 complete
- **Input:** Implementation (D3); acceptance criteria (R2)
- **Output:** Pass → D5; or failure with diagnosis
- **Exit conditions:** All acceptance criteria verified, or failure classified
- **Notes:** Two failure paths: implementation failure → D3; requirement failure → R2.

**[D5] Commit sorting**
- **Actor:** Git agent
- **Trigger:** D4 passes
- **Input:** All uncommitted changes in the worktree
- **Output:** One or more logical commits (Conventional Commits format)
- **Exit conditions:** All changes committed; user confirms commit groupings
- **Notes:** Proposed commits presented for user approval before executing. Never `git add -A`.

**[D6] PR creation / update**
- **Actor:** GitHub agent
- **Trigger:** D5 complete
- **Input:** Commit history on branch; open GitHub issues
- **Output:** Pull request with `Closes #N` references
- **Exit conditions:** PR exists and references all relevant issues
- **Notes:** Coverage analysis presented for user confirmation before acting.

**[D7] Adjacent work detection**
- **Actor:** GitHub agent (during D6)
- **Trigger:** Commit analysis reveals work not covered by any referenced issue
- **Input:** Uncovered commits from D6 analysis
- **Output:** (a) New GitHub issues for separate units of work; or (b) a note in PR body for useful adjacent work that stays
- **Exit conditions:** All commits accounted for by at least one issue
- **Notes:** Separate units of work become their own issues. Useful adjacent work stays in the PR with an explicit note and no stash/cherry-pick required.

**[P2] Merge PR**
- **Actor:** GitHub agent (`merge approve checkout`)
- **Trigger:** User requests merge
- **Input:** Open PR on current branch
- **Output:** PR merged; all `Closes #N` issues closed automatically
- **Exit conditions:** PR merged; worktree exited (`ExitWorktree action=remove`); default branch pulled
- **Notes:** Requires admin privileges. Feature command handles worktree exit and `git pull`.

### Cross-cutting Concerns

**[S1] Stakeholder input**
- **Actor:** User (or any stakeholder)
- **Trigger:** New information, changed priorities, or feedback — at any point
- **Output:** Redirection to the appropriate pipeline step
- **Notes:** S1 is an interrupt, not a step. It can arrive at any moment and redirect anywhere. The analyst or engineer acknowledges and resumes from the redirected point.

**[V1] State visualisation** *(future)*
- One state machine per user-initiated interaction; one per rose-initiated interaction (E5).
- Highlights current node for user and active agent nodes simultaneously.
- Preference for off-the-shelf tooling over custom build.

---

## Observability — Log Dump Specification

Agents emit structured logs as they move through the lifecycle. Hooks capture the tool-call stream automatically. Together they produce two resolution levels: **step-level** (agent-emitted) and **tool-level** (hook-emitted).

### File layout

```
~/.claude/logs/
└── <session-id>/
    ├── events.jsonl   # append-only, one JSON object per line
    └── meta.json      # session metadata; written at start, updated at end
```

`session-id` is extracted from the `session_id` field of the JSON payload that Claude Code passes on stdin to every hook. `log-session-start.sh` also writes the active session ID to `~/.claude/logs/.active-session` so that agents (which do not receive hook stdin) can discover the correct log directory. One directory per session.

---

### `meta.json`

Written once at `session.start`, updated at `session.end`.

```json
{
  "session_id": "abc123",
  "interaction_id": "feat/42-my-feature",
  "entry_point": "E1",
  "started_at": "2026-03-23T10:00:00.000Z",
  "ended_at": "2026-03-23T10:45:00.000Z",
  "status": "in_progress | completed | interrupted",
  "outcome": "delivery | investigation | abandoned | null"
}
```

---

### `events.jsonl`

Every event shares this envelope:

```json
{
  "ts": "2026-03-23T10:15:30.123Z",
  "session_id": "abc123",
  "seq": 42,
  "source": "agent | hook",
  "agent": "analyst | engineer | git | github | orchestrator",
  "step": "R1 | R2 | R3 | R4 | R5 | D1 | D2 | D3 | D4 | D5 | D6 | D7 | P2 | W1 | S1",
  "event": "<event-type>",
  "payload": {}
}
```

`seq` is a monotonically increasing integer within the session. Use it to order events when filesystem timestamps collide.

---

### Event types

| `event` | `source` | `payload` keys | Meaning |
|---------|----------|----------------|---------|
| `session.start` | hook | `entry_point`, `description` | Session opened |
| `session.end` | hook | `outcome`, `final_step` | Session closed |
| `step.enter` | agent | `from` (prior step or null) | Agent has begun this step |
| `step.exit` | agent | `to` (next step), `outcome` (`confirmed \| looped \| failed`) | Agent is leaving this step |
| `transition` | agent | `from`, `to`, `reason` | Decision gate or S1 redirect |
| `tool.call` | hook | `tool`, `input` (object, truncated at 500 chars) | Tool invocation |
| `tool.result` | hook | `tool`, `exit_code` (for Bash), `truncated` (bool) | Tool result |
| `message.user` | hook | `preview` (first 120 chars) | User sent a message |
| `message.agent` | hook | `preview` (first 120 chars) | Agent replied |
| `interrupt.s1` | agent | `redirect_to`, `note` | Stakeholder interrupt acknowledged |
| `error` | agent \| hook | `message`, `recoverable` (bool) | Something went wrong |

---

### How agents emit step events

Every agent emits `step.enter` and `step.exit` via inline Bash at each step boundary. Agents do not receive hook stdin, so they read the active session ID from the breadcrumb file written by `log-session-start.sh`:

```bash
SESSION_ID=$(cat "$HOME/.claude/logs/.active-session" 2>/dev/null || echo "unknown")
LOG_DIR="$HOME/.claude/logs/$SESSION_ID"
mkdir -p "$LOG_DIR"
SEQ=$(( $(wc -l < "$LOG_DIR/events.jsonl" 2>/dev/null || echo 0) + 1 ))
TS=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")
printf '%s\n' "{\"ts\":\"$TS\",\"session_id\":\"$SESSION_ID\",\"seq\":$SEQ,\"source\":\"agent\",\"agent\":\"<name>\",\"step\":\"<code>\",\"event\":\"step.enter\",\"payload\":{\"from\":null}}" >> "$LOG_DIR/events.jsonl"
```

Agents use inline Bash rather than an external script — the hook layer handles the tool-call stream; agents handle step boundaries.

---

### How hooks capture tool events

Three hooks in `global/hooks/` are bound in `settings.json`:

| Hook script | Bound to | Does |
|-------------|----------|------|
| `log-session-start.sh` | `PreToolUse` (fires once via sentinel) | Reads `session_id` from stdin JSON; creates log dir, writes `meta.json`, writes `.active-session` breadcrumb, emits `session.start` |
| `log-tool-event.sh` | `PostToolUse` | Reads stdin JSON once, extracts both `session_id` and tool payload; appends `tool.call` event |
| `log-session-end.sh` | `Stop` | Reads `session_id` from stdin JSON; derives outcome from last `step.exit`, appends `session.end`, updates `meta.json` |

---

### What the observability app will consume

A future app tails `events.jsonl` and:
- Highlights the current step node (most recent `step.enter` with no matching `step.exit`)
- Shows active agents on their nodes
- Renders a scrollable event stream in a side panel

Format: newline-delimited JSON, append-only. Any `tail -f`-based reader works with no setup. Preference for off-the-shelf tooling over a custom build.

---

## Testing changes

With `ROSE_DEV=$HOME/rose` set (already in your `~/.zshrc`), rose rebuilds from this directory on every run:

```bash
rose reinstall    # wipe ~/.claude and reinstall from this branch's source
```

Switch branches freely — `rose reinstall` always installs from the current checkout.
