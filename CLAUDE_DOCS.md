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

### `agent-{agentId}.meta.json`

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

### `agent-{agentId}.jsonl`

The subagent's own full conversation transcript, in the same format as a parent session transcript (`user`, `assistant`, `progress` entries). Key fields:

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

Note `isSidechain: true` — this marks all subagent entries as belonging to a sidechain, not the main conversation. `sessionId` is the **parent** session's ID.

From this file we extract:

| Field | How |
|---|---|
| `started_at` | `timestamp` of first entry |
| `size_kb` | file size on disk |
| `tool_use_count` | count of `tool_use` blocks across all `assistant` entries |

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

#### 2 — Agent running (`progress` entries)

While the agent works, a stream of `progress` entries arrives, all sharing the same `parentToolUseID`:

```json
{
  "type": "progress",
  "timestamp": "2026-04-06T12:06:31.536Z",
  "parentToolUseID": "toolu_vrtx_01CkwKbLK1PpkVbt6a9NSzmZ",
  "toolUseID": "agent_msg_vrtx_01E17...",
  "isSidechain": false,
  "data": {
    "type": "agent_progress",
    "agentId": "a69d496525515eb5e",
    "prompt": "What are all the possible hooks...",
    "message": { "..." : "..." }
  }
}
```

Key observations:
- `data.agentId` is the join key to the `subagents/` directory (filename `agent-{agentId}.*`)
- `parentToolUseID` is the join key back to the `tool_use` block in the `assistant` entry
- `agentName` is always `null` — the human-readable name is only in the `tool_use` input or `.meta.json`
- There can be dozens of these per invocation — one per streamed chunk

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