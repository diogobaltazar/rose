# Claude Code — Concepts & Reference

Notes on Claude Code's behaviour, built up from docs research and most importantly, testing and verification.

---

## Configuration

Claude Code configuration is split across two files:

### `~/.claude/settings.json`

Runtime settings — hooks, permissions, env vars. Managed by `rose install`.

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: "1"` is required to enable agent teams (teammates). Without it, the `Agent` tool only supports subagents.

### `~/.claude.json`

User preferences — UI, model, feature flags. Edited directly (not managed by `rose install`).

```json
{
  "teammateMode": "in-process"
}
```

`teammateMode: "in-process"` controls how teammates are spawned. Must be set here, not in `settings.json`.

---

## Session

A **session** is the continuous conversation context identified by a single `session_id` UUID. It begins when you launch (or resume) Claude Code and ends when you exit.

Key properties:

- Persists across many **[turns](#turn)** — each user message + assistant response is one turn inside the session
- Can be **resumed** — the same `session_id` continues, with the same transcript
- Can be **compacted** — the transcript is summarised, but the session carries on
- The `session_id` is stable for the entire lifetime of the conversation

---

## Turn

A **turn** is one complete request-response cycle within a session: the user submits a message, Claude thinks, uses tools, and finishes.

| Hook | Fires when |
|---|---|
| `UserPromptSubmit` | A turn begins (user submits a message); carries the prompt text |
| `Stop` | A turn ends (Claude finishes responding); carries `stop_reason` |

A [session](#session) contains many turns. `Stop` firing does not mean the session has ended.

---

## Claude Code Native Storage

Claude Code stores session data in two locations used as the source of truth for observability.

### Project

A **project** is a working directory. `~/.claude/projects/` has one subdirectory per unique `cwd`, named by encoding the path with `/` replaced by `-`. All sessions started from that directory live inside it.

```
~/.claude/projects/
└── -{absolute}-{pathto}-{project}/       ← e.g.: /Users/pereid22/rose
    ├── {session_id}.jsonl
    └── {session_id}.jsonl
```

### Transcript

A **transcript** is the full record of a session's conversation. Every entry in a **project** (see above) (e.g.: user messages, assistant responses, tool calls, tool results, system prompts) is appended as a JSON line to `{session_id}.jsonl`. Claude Code replays this file when resuming a session.

### `~/.claude/sessions/{pid}.json`

One file per running Claude Code process:

```json
{
  "pid":       71823,
  "sessionId": "dedd37bc-...",
  "cwd":       "/Users/pereid22/rose",
  "startedAt": 1775477968105
}
```

**Critical:** `sessionId` here is the **process identity**, not the transcript filename. On a fresh session they match. On a resume they diverge — the process gets a new `sessionId` (`dedd37bc`) but continues appending to the original transcript (`78b85df3.jsonl`).

```
Fresh session:
  sessions/12345.json  →  sessionId: 78b85df3
  projects/.../78b85df3.jsonl  ← created, entries have sessionId: 78b85df3  ✓ match

Resume:
  sessions/71823.json  →  sessionId: dedd37bc  (new process ID)
  projects/.../78b85df3.jsonl  ← still being written to, entries still have sessionId: 78b85df3  ✗ no match
  projects/.../dedd37bc.jsonl  ← never created
```

#### Mapping a live process to its transcript

`sessionId` in `sessions/{pid}.json` cannot be used to find the transcript on resume. Instead, use `cwd` + `startedAt`:

1. Encode `cwd` → project directory name
2. Find the `.jsonl` in that directory with `mtime >= startedAt / 1000`
3. That is the transcript being actively written to

This works because only one transcript per project can be modified after the process started.

### `~/.claude/projects/{encoded-cwd}/{session_id}.jsonl`

Full conversation transcript for each session, scoped to the working directory. The directory name is the cwd with `/` replaced by `-` (e.g. `/Users/pereid22/rose` → `-Users-pereid22-rose`). This is what `/resume` reads.

Each line is a JSON object. The two relevant entry types are `user` and `assistant`. Tool results are also `user` type (with `message.content` as an array). The fields we care about:

```json
{
  "type": "user",
  "sessionId": "8ac36fae-...",
  "timestamp": "2026-04-06T02:41:49.059Z",
  "gitBranch": "main",
  "cwd": "/Users/pereid22/rose",
  "message": {
    "role": "user",
    "content": "there are hooks in global/hooks that I no longer require"
  }
}
```

```json
{
  "type": "assistant",
  "timestamp": "2026-04-06T02:41:52.000Z",
  "message": {
    "role": "assistant",
    "stop_reason": "end_turn",
    "content": [
      { "type": "text", "text": "Which hooks would you like removed?" }
    ]
  }
}
```

Key fields for `observe.py --list`:

| Field | Where |
|---|---|
| `title` | `message.content` of first `user` entry where content is a plain string |
| `branch` | `gitBranch` of first `user` entry |
| `started_at` | `timestamp` of first entry in the file |
| `ended_at` | `timestamp` of last entry in the file (or file mtime) |

---

## Teammates vs Subagents

Both teammates and subagents are invoked via the `Agent` tool. The distinction is in how they are spawned and whether they can send messages back.

### Subagents

Spawned with `Agent(subagent_type: "...", prompt: "...")`. Run inline, return a result, done. No messaging, no team.

### Teammates

Spawned with `Agent(subagent_type: "...", name: "...", team_name: "...")`. Can send and receive messages via `SendMessage`. Coordinated by a team lead.

### Are teammates separate OS processes?

**No.** With `teammateMode: "in-process"` (set in `~/.claude.json`), teammates run inside the same Claude Code process as the parent session. This is confirmed by:

- `~/.claude/sessions/` contains only one entry — the parent session's PID. No additional entries appear when teammates are launched.
- The teammate shutdown response includes `"paneId": "in-process"` and `"backendType": "in-process"`.
- Teammates appear in `observe --list` as subagents under the parent session, not as top-level sessions.

**Consequence:** there are no teammate PIDs to display. Everything runs under the parent session's PID.

### Storage

Teammates and subagents use identical native storage — both appear in `{session_id}/subagents/`:

```
~/.claude/projects/{encoded-cwd}/{session_id}/subagents/
├── agent-{agentId}.meta.json    ← agentType: "rose-backlog", description: "..."
└── agent-{agentId}.jsonl        ← full conversation transcript
```

The only way to distinguish a teammate invocation from a plain subagent invocation in the transcript is context — teammates are typically spawned with a `name` and `team_name`.

---

## Agent Storage

Every subagent invocation is recorded in two places: the **parent transcript** (which sees the agent as a tool call) and a dedicated **subagent directory** (which holds its own full conversation).

### Directory layout

```
~/.claude/projects/{encoded-cwd}/
├── {session_id}.jsonl                          # parent transcript
└── {session_id}/
    ├── subagents/
    │   ├── agent-{agentId}.meta.json           # agentType + description
    │   └── agent-{agentId}.jsonl               # full subagent conversation
    └── tool-results/
```

`{agentId}` is a runtime identifier (e.g. `a69d496525515eb5e`) generated fresh for each invocation. It is **not** the `subagent_type` name — it is the join key between the subagent files and the parent transcript entries.

---

### `{session}/agent-{agentId}.meta.json`

The human-readable label and purpose for this invocation:

```json
{
  "agentType": "claude-code-guide",
  "description": "Claude Code hooks reference"
}
```

- `agentType` is the named agent (`rose`, `rose-backlog`, `claude-code-guide`, etc.)
- `description` is the short label Claude passed when invoking the agent — it distinguishes two runs of the same `agentType`

---

### `{session}/agent-{agentId}.jsonl`

The subagent's own full conversation transcript, in the same format as a parent session transcript (`user`, `assistant`, `progress` entries).

**First entry — the prompt (`user`):**

```json
{
  "type": "user",
  "agentId": "a69d496525515eb5e",
  "sessionId": "78b85df3-9ce0-4d1d-a4ce-2d7459980b92",
  "isSidechain": true,
  "timestamp": "2026-04-06T12:06:29.891Z",
  "cwd": "/Users/pereid22/rose",
  "message": {
    "role": "user",
    "content": "What are all the possible hooks that Claude Code provides?..."
  }
}
```

`isSidechain: true` marks all subagent entries as belonging to a sidechain, not the main conversation. `sessionId` is the **parent** session's ID. The `timestamp` of this first entry is the agent's `started_at`.

**Tool call inside the subagent (`assistant`):**

```json
{
  "type": "assistant",
  "agentId": "a69d496525515eb5e",
  "sessionId": "78b85df3-9ce0-4d1d-a4ce-2d7459980b92",
  "isSidechain": true,
  "timestamp": "2026-04-06T12:06:31.535Z",
  "message": {
    "model": "claude-haiku-4-5-20251001",
    "role": "assistant",
    "stop_reason": "tool_use",
    "content": [
      {
        "type": "tool_use",
        "id": "toolu_vrtx_019zxiz3j8zvkSjZLwvB9TTt",
        "name": "WebFetch",
        "input": {
          "url": "https://...",
          "prompt": "List of all available hooks in Claude Code"
        }
      }
    ]
  }
}
```

Each `tool_use` block in `assistant` entries counts toward `tool_use_count`. Note the subagent runs on `claude-haiku` by default, not the parent model.

From this file we extract:

| Field | How |
|---|---|
| `started_at` | `timestamp` of first entry |
| `size_kb` | file size on disk |
| `tool_use_count` | count of `tool_use` blocks across all `assistant` entries |

**Hook events inside the subagent (`progress`):**

The subagent's `.jsonl` also contains `progress` entries — but these are **hook notifications for the subagent's own tool calls**, not streaming output. They are unrelated to the parent-transcript join.

```json
{
  "type": "progress",
  "agentId": "a69d496525515eb5e",
  "sessionId": "78b85df3-9ce0-4d1d-a4ce-2d7459980b92",
  "isSidechain": true,
  "timestamp": "2026-04-06T12:06:31.537Z",
  "toolUseID": "toolu_vrtx_019zxiz3j8zvkSjZLwvB9TTt",
  "parentToolUseID": "toolu_vrtx_019zxiz3j8zvkSjZLwvB9TTt",
  "data": {
    "type": "hook_progress",
    "hookEvent": "PreToolUse",
    "hookName": "PreToolUse:WebFetch",
    "command": "~/.claude/hooks/log-session-start.sh"
  }
}
```

`data.type: "hook_progress"` — this is the subagent's own PreToolUse hook firing before its WebFetch call. Not useful for lifecycle tracking.

---

### How agent lifecycle is recorded in the parent transcript

Each agent invocation leaves three kinds of entries in the **parent** `{session_id}.jsonl`, all linked by a common `tool_use_id`:

#### 1 — Agent starts (`assistant` entry)

When Claude decides to invoke an agent, it writes an `assistant` entry with a `tool_use` block:

```json
{
  "type": "assistant",
  "timestamp": "2026-04-06T12:06:29.778Z",
  "message": {
    "role": "assistant",
    "content": [
      {
        "type": "tool_use",
        "id": "toolu_vrtx_01CkwKbLK1PpkVbt6a9NSzmZ",
        "name": "Agent",
        "input": {
          "subagent_type": "claude-code-guide",
          "description": "Claude Code hooks reference",
          "prompt": "What are all the possible hooks...",
          "run_in_background": false
        }
      }
    ]
  }
}
```

`id` is the `tool_use_id` anchor — everything else joins on this.

#### 2 — Agent running (`progress` entries in the **parent** transcript)

While the agent works, `progress` entries with `data.type: "agent_progress"` stream into the **parent** transcript. These are distinct from the `hook_progress` entries in the subagent's own `.jsonl`.

```json
{
  "type": "progress",
  "isSidechain": false,
  "timestamp": "2026-04-06T12:06:29.891Z",
  "parentToolUseID": "toolu_vrtx_01CkwKbLK1PpkVbt6a9NSzmZ",
  "toolUseID": "agent_msg_vrtx_01E17jvrb19jEjp7mEBXzTtc",
  "sessionId": "78b85df3-9ce0-4d1d-a4ce-2d7459980b92",
  "data": {
    "type": "agent_progress",
    "agentId": "a69d496525515eb5e",
    "prompt": "What are all the possible hooks that Claude Code provides?...",
    "message": {
      "type": "user",
      "message": { "role": "user", "content": [{ "type": "text", "text": "..." }] }
    }
  }
}
```

Key observations:
- `data.type: "agent_progress"` — distinguishes these from `hook_progress` entries
- `data.agentId` — join key to `subagents/agent-{agentId}.*` files
- `parentToolUseID` — join key back to the `tool_use.id` in the `assistant` entry (step 1)
- `isSidechain: false` — these live in the main conversation, not the subagent's sidechain
- `agentName` is always absent — the human-readable name is only in `.meta.json` or the `tool_use` input
- There can be dozens per invocation — one per streamed chunk

**Critical for status detection:** these entries only appear once the agent begins streaming output. In the brief window after the subagent file appears but before the first chunk arrives, no `agent_progress` entry exists yet — meaning the `agentId → tool_use_id` link cannot be established from the transcript alone.

#### 3 — Agent finishes (`user` entry)

When the agent completes, a `user` entry appears with a `tool_result` block:

```json
{
  "type": "user",
  "timestamp": "2026-04-06T12:07:15.303Z",
  "message": {
    "role": "user",
    "content": [
      {
        "type": "tool_result",
        "tool_use_id": "toolu_vrtx_01CkwKbLK1PpkVbt6a9NSzmZ",
        "content": [
          { "type": "text", "text": "Based on the documentation..." }
        ]
      }
    ]
  }
}
```

`tool_use_id` matches the `id` from the `assistant` entry. Its `timestamp` minus the start `timestamp` gives the exact duration.

---

### How `observe.py` joins everything

```
subagents/agent-{agentId}.meta.json   →  agentType, description
subagents/agent-{agentId}.jsonl       →  started_at, size_kb, tool_use_count

parent transcript:
  progress entry  data.agentId == agentId  →  parentToolUseID
  user entry      tool_result.tool_use_id == parentToolUseID  →  agent is done
```

Concretely, for each subagent:

1. Read `{agentId}` from the filename of `agent-*.meta.json`
2. Read `agentType` and `description` from the meta file
3. Read `started_at`, `size_kb`, `tool_use_count` from `agent-{agentId}.jsonl`
4. Scan parent transcript `progress` entries where `data.agentId == agentId` to get `parentToolUseID`
5. Scan parent transcript `user` entries for a `tool_result` where `tool_use_id == parentToolUseID`
6. If a matching `tool_result` exists → agent is **done**; if not and session is live → agent is **live**

Timeline in the parent transcript for one agent invocation:

```
assistant  [12:06:29]  tool_use      id=toolu_01Ck  name=Agent  subagent_type=claude-code-guide
progress   [12:06:31]  agent_progress  parentToolUseID=toolu_01Ck  agentId=a69d...  (chunk 1)
progress   [12:06:33]  agent_progress  parentToolUseID=toolu_01Ck  agentId=a69d...  (chunk 2)
...
user       [12:07:15]  tool_result   tool_use_id=toolu_01Ck  ← agent done, duration = 46s
```

---

## SubagentStart / SubagentStop Hook Payloads

Claude Code fires two hooks around every subagent invocation. Both are separate from the native storage — they write to `~/.claude/logs/subagent-events.jsonl` (or wherever the hook script writes them) and provide an **authoritative, real-time signal** for live/done status that does not depend on the tool_result join.

### SubagentStart

Fires the moment the subagent begins. The payload does **not** yet include the transcript path (the file may not exist).

```json
{
  "session_id": "78b85df3-9ce0-4d1d-a4ce-2d7459980b92",
  "transcript_path": "/Users/pereid22/.claude/projects/-Users-pereid22-rose/78b85df3-9ce0-4d1d-a4ce-2d7459980b92.jsonl",
  "cwd": "/Users/pereid22/rose",
  "agent_id": "a73f163bf6391f728",
  "agent_type": "rose-backlog",
  "hook_event_name": "SubagentStart"
}
```

Note: `transcript_path` here is the **parent** session transcript, not the subagent's own `.jsonl`.

### SubagentStop

Fires when the subagent finishes. Adds the subagent transcript path and the last assistant message.

```json
{
  "session_id": "78b85df3-9ce0-4d1d-a4ce-2d7459980b92",
  "agent_id": "a73f163bf6391f728",
  "agent_type": "rose-backlog",
  "hook_event_name": "SubagentStop",
  "stop_hook_active": false,
  "agent_transcript_path": "/Users/pereid22/.claude/projects/-Users-pereid22-rose/78b85df3-9ce0-4d1d-a4ce-2d7459980b92/subagents/agent-a73f163bf6391f728.jsonl",
  "last_assistant_message": "Task complete. Read one file, reported back to team-lead."
}
```

Key fields:

| Field | Present in | Notes |
|---|---|---|
| `session_id` | Both | Parent session UUID |
| `agent_id` | Both | Join key to `subagents/agent-{agentId}.*` files |
| `agent_type` | Both | Named agent type (e.g. `rose-backlog`) |
| `hook_event_name` | Both | `"SubagentStart"` or `"SubagentStop"` |
| `transcript_path` | Start only | Parent transcript path |
| `agent_transcript_path` | Stop only | Subagent's own `.jsonl` |
| `last_assistant_message` | Stop only | Final message text from the subagent |
| `stop_hook_active` | Stop only | Whether a `Stop` hook is also active |

---

## Agent Live/Done Detection in `observe.py`

Determining whether a subagent is still running is non-trivial. Three signals are available, in decreasing order of reliability.

### Tier 1 — Hook log (authoritative)

`~/.claude/logs/subagent-events.jsonl` is written by `log-subagent-events.sh`, registered under both `SubagentStart` and `SubagentStop`. Reading this file forward and keeping the last event per `agent_id` gives an exact signal:

```
SubagentStart  →  "live"
SubagentStop   →  "done"
```

The `agent_id` in the hook payload matches the filename stem of `subagents/agent-{agentId}.jsonl`, so no join is needed. This is the preferred signal; it is accurate from the very first millisecond of the agent's life.

### Tier 2 — Tool-result join (slight timing gap)

For sessions that predate the hooks, `observe.py` falls back to the transcript join documented in [How `observe.py` joins everything](#how-observepy-joins-everything):

```
agent_progress entry  →  parentToolUseID
tool_result entry     →  agent is done
```

The gap: `agent_progress` entries only appear after the agent begins streaming. In the brief window between `SubagentStart` and the first chunk, no `agent_progress` entry exists, so the agent appears to have no link and the fallback fires. This was the motivation for Tier 1.

### Tier 3 — Conservative default

If neither signal is available (old session, no hook log, no transcript link), the agent is assumed **done**. This avoids phantom live dots on historical sessions.

### Why SubagentStop can be missed

`SubagentStop` does not fire if the parent Claude Code process exits abruptly, or if the context limit is hit while an agent is mid-flight. This leaves an orphaned `SubagentStart` in the hook log, with no corresponding `SubagentStop`. If observed naïvely, such an agent appears live forever.

The tool-result join is immune to this: it is written by Claude Code into the parent transcript, not by a hook, so it is reliable even when hooks fail to fire. This makes it the correct cross-check when the hook log says "live".

### Decision tree

```
SubagentStop fired for this agent_id?
├─ yes → done                                       (hook log — definitive)
└─ no  → tool_result present in parent transcript?
          ├─ yes → done                             (transcript join — SubagentStop missed)
          └─ no  → SubagentStart fired?
                    ├─ yes → live                   (genuinely in progress)
                    └─ no  → done                   (no signal — conservative default)
```

After computing `is_done`, status is clamped: a "live" agent in a dead session is still shown as "done".

---

## Claude Code Memory System

Claude Code supports a file-based memory system that persists facts across sessions. It is configured per-project and loaded automatically into context at the start of every conversation.

### Location

```
~/.claude/projects/{encoded-cwd}/memory/
├── MEMORY.md          ← index file, loaded into every conversation
└── {name}.md          ← individual memory entries
```

`MEMORY.md` is the index. It must stay concise (lines after ~200 are truncated) and contain only links to individual memory files — never memory content directly.

### Memory types

| Type | Purpose |
|---|---|
| `user` | Who the user is — role, expertise, preferences |
| `feedback` | Corrections and confirmed approaches ("don't do X", "yes, exactly that") |
| `project` | Ongoing context, goals, decisions, deadlines |
| `reference` | Pointers to non-obvious facts that would otherwise have to be rediscovered |

### Entry format

Each memory file uses frontmatter:

```markdown
---
name: SubagentStop reliability
description: SubagentStop does not fire on abrupt exit or context limit
type: reference
---

Content here. For feedback and project types, structure as:
rule/fact, then **Why:** and **How to apply:** lines.
```

### What to save and what not to

Save things that are **non-obvious and durable**: behavioural findings, confirmed design decisions, user preferences, external resource locations.

Do **not** save things derivable from the code or git history: file paths, architecture, conventions, recent changes, in-progress work, or anything already in CLAUDE.md files.