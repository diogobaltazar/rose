# Behavioural Documentation of AI Orchestration Systems
## Volume I: Claude Code

**Version:** 1.0
**Date:** 2026-04-07
**Repository:** [diogobaltazar/rose](https://github.com/diogobaltazar/rose)

---

## Abstract

This document is a formal behavioural reference for *AI orchestrators* — software systems that use AI components to make runtime decisions about task decomposition, tool invocation, and inter-agent coordination. Volume I focuses on **Claude Code** [1], Anthropic's command-line coding assistant, as a representative *coding agent orchestrator*.

Each documented behaviour is treated as a falsifiable property: a claim about system output under stated conditions. Where possible, the claim is accompanied by an executable experiment in the **rose** repository [R]. Each experiment constitutes a *lab* with explicit prerequisites (OS, installed software, LLM access, API credentials, configuration). A reader who satisfies the prerequisites can run the experiment and verify the claim independently; a reader who cannot may still use the experiment as a precise specification of what was observed. Reproducibility is conditional on prerequisite access, not universal.

The rose repository [R] provides the test apparatus: hook scripts, an observability API, and a session monitoring dashboard. A comparative survey of agentic frameworks is included to situate Claude Code in the broader ecosystem. Subsequent volumes will address Gastown [3], OpenClaw [2], and platform-hosted orchestrators.

---

## 1. Introduction

### 1.1 Methodology

AI orchestrators cannot be fully characterised by static analysis: their control flow is determined by model inference at runtime, not by explicit branching logic. This document uses an empirical, observation-based methodology governed by three principles:

1. **Condition specificity.** Every behaviour records the conditions under which it was observed: OS, software versions, configuration state.
2. **Reproducibility.** Each behaviour is, where possible, accompanied by an executable experiment in the **rose** repository [R] — a *lab* with explicit *prerequisites* a reader must satisfy to run it. Reproducibility is conditional on those prerequisites; the experiment is a precise specification regardless.
3. **Falsifiability.** Known failure modes and edge cases are stated alongside each nominal description.

### 1.2 Experimental Model

| Term | Definition |
|---|---|
| **Property** | A falsifiable claim about system behaviour under stated conditions |
| **Experiment** | Executable code that verifies a property by observing system output |
| **Lab** | The complete set of conditions required to run an experiment |
| **Prerequisites** | The lab conditions a reader must arrange before running the experiment |
| **Outcome** | The observable result compared against the documented property |

### 1.3 Defining the Orchestrator

An *AI orchestrator* is a system that:

1. Receives a high-level goal in natural language or a structured format.
2. Decomposes it into sub-tasks at **runtime** via model inference — not at design time.
3. Dispatches sub-tasks to specialised executors: tools, external APIs, or subordinate agents.
4. Integrates results and determines next steps without explicit human re-instruction.

This excludes static pipelines (decomposition at design time) and chatbots (no dispatch to external executors).

### 1.4 A Survey of Agentic Frameworks

The following survey situates Claude Code within the broader ecosystem. Each archetype is defined by what it orchestrates, how runtime decisions are made, and how state is persisted.

#### 1.4.1 Coding Agent Orchestrators

These systems decompose and execute software engineering tasks using a combination of file system tools, shell execution, code analysis, and subordinate agents. The decision of which tools to invoke and in what order is made by a model at inference time.

**Claude Code** [1] (Anthropic, TypeScript) is a CLI coding assistant in which the model is the decision layer, not a component plugged into a framework. It exposes a tool API — file operations, shell execution, web fetch, agent spawning, team messaging — and the model decides at each inference step which tools to call and whether to delegate. Claude Code supports hierarchical multi-agent teams, a hook system for observability, and JSONL-based session transcripts on disk. It is the exclusive subject of this volume.

**Gastown** [3] (gastownhall, Go) coordinates heterogeneous AI coding agents — Claude Code, Copilot, Codex, Gemini — across a shared workspace. Components: *Mayor* (primary coordinator), *Polecats* (workers with persistent identity but ephemeral sessions), *Rigs* (git project containers), *Hooks* (git worktree storage that survives crashes), *Convoys/Beads* (git-backed work tracking), *Refinery* (merge queue), *Wasteland* (federated network via DoltHub). Gastown is an *orchestrator of orchestrators*: it treats Claude Code as a Polecat. Its central design premise — agents lose context on restart — is addressed through git-backed state rather than in-process transcripts.

#### 1.4.2 Messaging-to-Agent Gateways

These systems route human messages from multiple communication channels to AI agents and execute device-local actions on their behalf. The orchestration concern is channel unification and message routing rather than task decomposition.

**OpenClaw** [2] (openclaw, TypeScript) is a personal AI assistant platform built around a WebSocket Gateway (`ws://127.0.0.1:18789`) that routes messages from 20+ channels (WhatsApp via Baileys, Telegram via grammY, Slack, Discord, etc.) to AI agents. Device nodes on macOS, iOS, and Android execute local actions (screen recording, camera, system commands); a dedicated Chromium instance provides browser control. **MyClaw** [4] provides managed cloud hosting for OpenClaw instances.

#### 1.4.3 Pipeline and Graph Orchestrators

These systems represent agent workflows as explicit computation graphs, where nodes are agents or processing components and edges — which may be conditional — determine control flow. Decomposition is defined at design time, but the AI components within nodes make local decisions at runtime.

**LangGraph** [5] (LangChain, Python/JavaScript) formalises workflows as directed graphs; nodes perform computation, edges are conditional transitions. Behaviour is inspectable at the graph level at the cost of requiring explicit topology design upfront.

**LangChain** [6] (LangChain, Python/JavaScript) provides chain and agent abstractions over LLMs. Its `AgentExecutor` implements a ReAct-style loop; the broader framework covers RAG, memory, and tool use. The most widely adopted orchestration library as of 2026.

**Haystack** [13] (deepset, Python) is a pipeline-oriented framework for document processing and RAG. Pipelines are directed acyclic graphs of components; it does not natively support autonomous multi-agent loops.

#### 1.4.4 Multi-Agent Conversation Frameworks

These systems coordinate groups of agents that communicate with one another through structured message passing. Orchestration concerns include role assignment, turn-taking, termination conditions, and result integration.

**AutoGen** [8] (Microsoft, Python) implements multi-agent conversation as a first-class abstraction. Agents communicate via a shared message bus; the framework manages turn-taking, termination, and human-in-the-loop. Supports both hierarchical and peer-to-peer topologies.

**CrewAI** [7] (CrewAI, Python) organises agents into *crews* with declared roles, goals, and backstories; delegation follows a sequential or hierarchical process. Positioned for enterprise workflow automation.

**Semantic Kernel** [9] (Microsoft, Python/.NET/Java) integrates LLMs into applications via a *kernel* managing plugins, memory, and planning. Strong in .NET/enterprise Microsoft environments; its planner generates and executes multi-step plans.

#### 1.4.5 Hosted Platform Orchestrators

These systems provide managed agent infrastructure through cloud APIs, abstracting away deployment, scaling, and runtime management. The developer declares agent capabilities; the platform handles execution.

**Amazon Bedrock Agents** [10] (AWS) provides managed agent runtimes on Bedrock foundation models. Developers declare *action groups* (Lambda-backed tools) and *knowledge bases* (RAG); the model plans invocation sequences at runtime.

**Google Vertex AI Agents** [11] (Google Cloud) provides tool-calling, grounding, and retrieval over Gemini. Agents deploy as managed endpoints; orchestration combines declarative configuration and model inference.

**OpenAI Assistants API** [12] (OpenAI) uses a *thread/run* model. Threads accumulate messages; runs execute the model with a defined tool set (code interpreter, file search, function calling). State is fully managed by OpenAI.

### 1.5 Comparative Summary

The frameworks surveyed above can be positioned along two principal axes: *what is being orchestrated* (the task domain) and *where decomposition decisions are made* (design time versus runtime).

| System | Archetype | Primary domain | Decomposition | State persistence |
|---|---|---|---|---|
| Claude Code [1] | Coding agent orchestrator | Software engineering | Runtime (model) | JSONL transcripts on disk |
| Gastown [3] | Orchestrator of orchestrators | Multi-agent coordination | Runtime (model) | Git worktrees + DoltHub |
| OpenClaw [2] | Messaging-to-agent gateway | Personal assistant | Runtime (model) | Managed container |
| LangGraph [5] | Graph orchestrator | General | Design time + runtime | User-defined |
| LangChain [6] | Chain/agent library | General | Runtime (ReAct loop) | Pluggable memory stores |
| AutoGen [8] | Multi-agent conversation | General | Runtime (group chat) | In-memory + optional |
| CrewAI [7] | Role-based crew | Enterprise workflows | Design time + runtime | In-memory |
| Semantic Kernel [9] | Enterprise AI integration | Enterprise/.NET | Runtime (planner) | Pluggable |
| Bedrock Agents [10] | Hosted platform | Cloud-native | Runtime (model) | AWS-managed |
| Vertex AI Agents [11] | Hosted platform | Cloud-native | Runtime (model) | GCP-managed |
| OpenAI Assistants [12] | Hosted platform | General | Runtime (model) | OpenAI-managed |
| Haystack [13] | Pipeline orchestrator | RAG / document processing | Design time | User-defined |

### 1.6 Scope of This Volume

This volume covers Claude Code across five domains:

| § | Domain |
|---|---|
| 2 | Configuration |
| 3 | Execution Model |
| 4 | Storage Architecture |
| 5 | Agent Architecture |
| 6 | Observability and Event Hooks |
| 7 | Memory System |

Gastown, OpenClaw, and the platform-hosted orchestrators will be addressed in subsequent volumes.

---

## 2. Configuration

**Lab prerequisites:** macOS Darwin 25.2.0; Claude Code installed; rose applied (`rose install` [R, `src/rose/cli/install.py`]).

Claude Code configuration lives in two files with distinct roles. Placing a key in the wrong file produces silently incorrect behaviour.

### 2.1 Configuration Scopes

`settings.json` is resolved across four scopes in decreasing precedence. For scalar values the highest-precedence scope wins; arrays are concatenated and de-duplicated; objects are deep-merged [1].

| Scope | Location | Shared |
|---|---|---|
| **Managed** | MDM/registry or `/Library/Application Support/ClaudeCode/managed-settings.json` | Yes (IT-deployed) |
| **Project** | `.claude/settings.json` | Yes (git-committed) |
| **Local** | `.claude/settings.local.json` | No (gitignored) |
| **User** | `~/.claude/settings.json` | No |

The JSON schema is published at `https://json.schemastore.org/claude-code-settings.json`; adding `"$schema"` to any `settings.json` enables editor autocomplete and inline validation [1].

### 2.2 `~/.claude/settings.json` — Full Reference

#### 2.2.1 Execution

| Key | Type | Description |
|---|---|---|
| `env` | `object` | Environment variables applied to every session. See notable values below |
| `model` | `string` | Override the default model (e.g. `"claude-sonnet-4-6"`) |
| `agent` | `string` | Run the main thread as a named subagent, inheriting its system prompt and tool restrictions |
| `effortLevel` | `"low"` \| `"medium"` \| `"high"` | Persist effort level across sessions. Written automatically by `/effort` |
| `alwaysThinkingEnabled` | `boolean` | Enable extended thinking by default |
| `autoUpdatesChannel` | `"latest"` \| `"stable"` | Update channel. `"stable"` is ~1 week old and skips regressed releases (default: `"latest"`) |
| `cleanupPeriodDays` | `number` | Delete sessions inactive longer than this many days (default: 30, minimum: 1) |
| `autoMemoryDirectory` | `string` | Custom directory for auto-memory storage. `~/`-expanded. Not valid in project settings |
| `plansDirectory` | `string` | Where plan files are stored, relative to project root (default: `~/.claude/plans`) |
| `defaultShell` | `"bash"` \| `"powershell"` | Shell for `!` commands. `"powershell"` requires `CLAUDE_CODE_USE_POWERSHELL_TOOL=1` |
| `includeGitInstructions` | `boolean` | Include built-in git workflow instructions in the system prompt (default: `true`) |
| `language` | `string` | Claude's preferred response language, e.g. `"japanese"` |
| `outputStyle` | `string` | Named output style applied via the system prompt |

**Notable `env` values:**

| Variable | Example value | Effect |
|---|---|---|
| `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` | `"1"` | Enable agent teams. Without this, `name`/`team_name` on `Agent` are silently ignored, `SendMessage` is unavailable, and `TeamCreate` has no effect [1] |
| `ANTHROPIC_BASE_URL` | `"http://localhost:8080"` | Override the API endpoint — used to route requests through a local proxy or gateway |
| `ANTHROPIC_AUTH_TOKEN` | `"sk-ant-..."` | API auth token sent as `Authorization: Bearer`. Overrides the token stored in `~/.claude.json` |
| `ANTHROPIC_CUSTOM_HEADERS` | `"x-portkey-metadata: {\"_user\":\"alice\"}"` | Arbitrary headers appended to every model request — used for proxy metadata, per-user tracking, or routing |
| `CLAUDE_CODE_ENABLE_TELEMETRY` | `"1"` | Enable OpenTelemetry telemetry export |
| `OTEL_METRICS_EXPORTER` | `"otlp"` | OpenTelemetry metrics exporter backend (used with `CLAUDE_CODE_ENABLE_TELEMETRY`) |
| `CLAUDE_CODE_USE_POWERSHELL_TOOL` | `"1"` | Required when `defaultShell` is set to `"powershell"` |
| `CLAUDE_CODE_DISABLE_GIT_INSTRUCTIONS` | `"1"` | Disable built-in git workflow instructions; takes precedence over `includeGitInstructions` |
| `CLAUDE_CODE_IDE_SKIP_AUTO_INSTALL` | `"1"` | Prevent automatic IDE extension installation |

#### 2.2.2 Permissions

The `permissions` object accepts:

| Key | Type | Description |
|---|---|---|
| `allow` | `string[]` | Rules to allow without prompting |
| `ask` | `string[]` | Rules to prompt for confirmation |
| `deny` | `string[]` | Rules to block unconditionally |
| `additionalDirectories` | `string[]` | Additional working directories for file access |
| `defaultMode` | `string` | Default permission mode at startup: `"default"`, `"acceptEdits"`, `"plan"`, `"auto"`, `"dontAsk"`, `"bypassPermissions"` |
| `disableBypassPermissionsMode` | `"disable"` | Prevent bypass-permissions mode and disable `--dangerously-skip-permissions` |
| `skipDangerousModePermissionPrompt` | `boolean` | Skip the confirmation prompt before entering bypass mode. Ignored in project settings |

**Rule syntax:** `Tool` or `Tool(specifier)`. Evaluation order: deny → ask → allow; first match wins.

| Example | Effect |
|---|---|
| `"Bash"` | All Bash commands |
| `"Bash(npm run *)"` | Commands beginning with `npm run` |
| `"Read(./.env)"` | Reading `.env` |
| `"WebFetch(domain:example.com)"` | Fetch requests to example.com |
| `"Bash(~/.claude/hooks/*.sh*)"` | Hook script execution |

#### 2.2.3 Hooks

The `hooks` object maps lifecycle event names to arrays of hook definitions [1].

| Event | Fires when |
|---|---|
| `PreToolUse` | Before a tool call; can block it |
| `PostToolUse` | After a tool call completes |
| `UserPromptSubmit` | The user submits a message |
| `Stop` | Claude finishes responding |
| `SubagentStart` | A subagent begins |
| `SubagentStop` | A subagent finishes |
| `Notification` | Claude Code sends a notification |

Hook definition structure:

```json
{
  "matcher": "ToolName",
  "hooks": [
    { "type": "command", "command": "path/to/script.sh" }
  ]
}
```

`matcher` is optional; when present, restricts the hook to a specific tool name. `PreToolUse` and `PostToolUse` support matchers; other events do not. HTTP hooks use `"type": "http"` with a `url` field.

Additional hook-related top-level keys:

| Key | Type | Description |
|---|---|---|
| `disableAllHooks` | `boolean` | Disable all hooks and any custom status line |
| `allowedHttpHookUrls` | `string[]` | Allowlist of URL patterns for HTTP hooks. `*` wildcard. Undefined = no restriction; `[]` = block all |
| `httpHookAllowedEnvVars` | `string[]` | Allowlist of env var names HTTP hooks may interpolate into headers |
| `statusLine` | `object` | Custom status line: `{"type": "command", "command": "path/to/script.sh"}` |

#### 2.2.4 API and Authentication

| Key | Type | Description |
|---|---|---|
| `apiKeyHelper` | `string` | Shell script (run via `/bin/sh`) that outputs an auth token sent as `X-Api-Key` and `Authorization: Bearer` |
| `awsAuthRefresh` | `string` | Script that modifies `.aws/` for Bedrock credential refresh |
| `awsCredentialExport` | `string` | Script that outputs JSON AWS credentials for Bedrock |
| `otelHeadersHelper` | `string` | Script for dynamic OpenTelemetry headers; run at startup and periodically |
| `forceLoginMethod` | `"claudeai"` \| `"console"` | Restrict login to one authentication method |
| `forceLoginOrgUUID` | `string` \| `string[]` | Require the authenticated account to belong to a specific organisation UUID |

#### 2.2.5 Model and Output

| Key | Type | Description |
|---|---|---|
| `availableModels` | `string[]` | Restrict selectable models. Does not affect the Default option |
| `modelOverrides` | `object` | Map Anthropic model IDs to provider-specific IDs (e.g. Bedrock ARNs) |
| `showThinkingSummaries` | `boolean` | Show extended thinking summaries in interactive sessions (default: `false`) |
| `attribution` | `object` | Git commit and PR attribution: `{"commit": "...", "pr": "..."}`. Empty string removes attribution |
| `autoMode` | `object` | Customize auto-mode classifier: `{"environment": [...], "allow": [...], "soft_deny": [...]}`. Not read from project settings |
| `disableAutoMode` | `"disable"` | Prevent auto mode; removes it from Shift+Tab cycle |
| `useAutoModeDuringPlan` | `boolean` | Use auto-mode semantics in plan mode (default: `true`). Not read from project settings |
| `respectGitignore` | `boolean` | Respect `.gitignore` in the `@` file picker (default: `true`) |

#### 2.2.6 Sandbox

The `sandbox` object configures bash command isolation (macOS, Linux, WSL2) [1]:

| Key | Type | Description |
|---|---|---|
| `enabled` | `boolean` | Enable sandboxing (default: `false`) |
| `failIfUnavailable` | `boolean` | Exit at startup if sandbox cannot start (default: `false`) |
| `autoAllowBashIfSandboxed` | `boolean` | Auto-approve bash when sandboxed (default: `true`) |
| `excludedCommands` | `string[]` | Commands that bypass the sandbox |
| `allowUnsandboxedCommands` | `boolean` | Allow `dangerouslyDisableSandbox` escape hatch (default: `true`) |
| `filesystem.allowWrite` | `string[]` | Additional paths sandboxed commands may write |
| `filesystem.denyWrite` | `string[]` | Paths sandboxed commands may not write |
| `filesystem.denyRead` | `string[]` | Paths sandboxed commands may not read |
| `filesystem.allowRead` | `string[]` | Re-allow reads within `denyRead` regions; takes precedence |
| `network.allowedDomains` | `string[]` | Permitted outbound network domains; wildcards supported |
| `network.allowUnixSockets` | `string[]` | Unix socket paths accessible in sandbox |
| `network.allowAllUnixSockets` | `boolean` | Allow all Unix socket connections (default: `false`) |
| `network.allowLocalBinding` | `boolean` | Allow binding to localhost ports, macOS only (default: `false`) |
| `network.httpProxyPort` | `number` | HTTP proxy port; if unset, Claude runs its own proxy |
| `network.socksProxyPort` | `number` | SOCKS5 proxy port |
| `enableWeakerNestedSandbox` | `boolean` | Weaker sandbox for unprivileged Docker (Linux/WSL2). **Reduces security** |
| `enableWeakerNetworkIsolation` | `boolean` | Allow TLS trust service in sandbox, macOS only. **Reduces security** |

Filesystem paths accept `/` (absolute), `~/` (home-relative), and `./` or no prefix (project-root-relative in project settings; `~/.claude`-relative in user settings).

#### 2.2.7 Worktree

| Key | Type | Description |
|---|---|---|
| `worktree.symlinkDirectories` | `string[]` | Directories to symlink from the main repo into each worktree (e.g. `["node_modules"]`) |
| `worktree.sparsePaths` | `string[]` | Directories to materialise via git sparse-checkout (cone mode) |

#### 2.2.8 UI

| Key | Type | Description |
|---|---|---|
| `fileSuggestion` | `object` | Custom script for `@` file autocomplete: `{"type": "command", "command": "..."}` |
| `prefersReducedMotion` | `boolean` | Reduce UI animations |
| `spinnerTipsEnabled` | `boolean` | Show tips in spinner (default: `true`) |
| `spinnerTipsOverride` | `object` | Custom spinner tips: `{"excludeDefault": true, "tips": [...]}` |
| `spinnerVerbs` | `object` | Custom action verbs: `{"mode": "append"/"replace", "verbs": [...]}` |
| `showClearContextOnPlanAccept` | `boolean` | Show "clear context" on plan accept screen (default: `false`) |
| `companyAnnouncements` | `string[]` | Announcements shown at startup, cycled at random |
| `feedbackSurveyRate` | `number` | Probability (0–1) that the session quality survey appears |
| `fastModePerSessionOptIn` | `boolean` | When `true`, fast mode resets to off each session |
| `voiceEnabled` | `boolean` | Enable push-to-talk voice dictation. Requires Claude.ai account |

#### 2.2.9 MCP Servers

| Key | Type | Description |
|---|---|---|
| `enableAllProjectMcpServers` | `boolean` | Auto-approve all MCP servers in project `.mcp.json` files |
| `enabledMcpjsonServers` | `string[]` | Specific `.mcp.json` servers to approve |
| `disabledMcpjsonServers` | `string[]` | Specific `.mcp.json` servers to reject |

#### 2.2.10 Managed-Only Settings

These keys are honoured only in managed settings sources (MDM, registry, or `managed-settings.json`). They are ignored in user, project, or local settings [1].

| Key | Type | Description |
|---|---|---|
| `allowManagedPermissionRulesOnly` | `boolean` | Prevent user/project settings from defining `allow`, `ask`, or `deny` rules |
| `allowManagedHooksOnly` | `boolean` | Prevent loading of user, project, and plugin hooks |
| `allowManagedMcpServersOnly` | `boolean` | Only the managed-settings MCP allowlist is respected |
| `allowedMcpServers` | `object[]` | Allowlist of MCP servers users may configure |
| `deniedMcpServers` | `object[]` | Denylist of MCP servers; takes precedence over the allowlist |
| `allowedChannelPlugins` | `object[]` | Allowlist of channel plugins that may push messages |
| `channelsEnabled` | `boolean` | Allow channels for Team/Enterprise users |
| `forceRemoteSettingsRefresh` | `boolean` | Block startup until remote managed settings are freshly fetched |
| `blockedMarketplaces` | `object[]` | Blocklist of plugin marketplace sources |
| `strictKnownMarketplaces` | `object[]` | Allowlist of plugin marketplaces users may add |
| `pluginTrustMessage` | `string` | Custom text appended to the plugin trust warning |
| `disableSkillShellExecution` | `boolean` | Disable inline shell execution in user/project/plugin skills |
| `disableDeepLinkRegistration` | `"disable"` | Prevent `claude-cli://` protocol handler registration |

### 2.3 `~/.claude.json` — Global Config

Preferences stored here rather than in `settings.json`. Adding these keys to `settings.json` triggers a schema validation error [1].

| Key | Type | Description |
|---|---|---|
| `teammateMode` | `"in-process"` \| `"tmux"` \| `"auto"` | How teammates are spawned. `auto` uses split panes in tmux/iTerm2, otherwise in-process |
| `editorMode` | `"normal"` \| `"vim"` | Key binding mode for the input prompt (default: `"normal"`) |
| `showTurnDuration` | `boolean` | Show turn duration after responses (default: `true`) |
| `terminalProgressBarEnabled` | `boolean` | Show terminal progress bar in supported terminals (default: `true`) |
| `autoConnectIde` | `boolean` | Auto-connect to a running IDE from an external terminal (default: `false`) |
| `autoInstallIdeExtension` | `boolean` | Auto-install the IDE extension from a VS Code terminal (default: `true`) |

`~/.claude.json` also stores the OAuth session, MCP server configurations (user and local scopes), per-project tool trust state, and various caches. Project-scoped MCP servers are stored in `.mcp.json`.

**Condition:** `teammateMode: "in-process"` must be set in `~/.claude.json`; setting it in `settings.json` has no effect. See §5.2.

---

## 3. Execution Model

**Lab prerequisites:** macOS Darwin 25.2.0; Claude Code installed; rose applied (`rose install` [R]).

### 3.1 Session

A **session** is the continuous conversation context identified by a stable UUID (`session_id`), instantiated on launch or resume and persisting until process exit.

- Contains one or more **turns** (§3.2).
- **Resumed:** same `session_id`, transcript replayed, new entries appended.
- **Compacted:** transcript summarised, `session_id` preserved, session continues.
- `session_id` is invariant across compaction, context window resets, and branch changes.

### 3.2 Turn

A **turn** is one request-response cycle: the user submits a message; the model reasons, invokes zero or more tools, and responds.

| Hook event | Fires when |
|---|---|
| `UserPromptSubmit` | Turn begins; carries the prompt text |
| `Stop` | Turn ends; carries `stop_reason` |

`Stop` signals end-of-turn, not end-of-session.

---

## 4. Storage Architecture

**Lab prerequisites:** macOS Darwin 25.2.0; Claude Code installed; rose applied (`rose install` [R]); at least one Claude Code session started from the project directory. All file paths and JSON schemas presented here were verified by direct observation of the live filesystem.

Claude Code maintains two storage categories: the **project transcript store** and the **session process registry** — the authoritative source of truth for all observability tooling [R, `src/rose/api/main.py`].

### 4.1 Project Transcript Store

#### 4.1.1 Directory Layout

A *project* in Claude Code's storage model corresponds to a working directory (`cwd`). All sessions originating from a given `cwd` are grouped under a single project directory:

```
~/.claude/projects/
└── {encoded-cwd}/
    ├── {session_id}.jsonl
    └── {session_id}.jsonl
```

The `encoded-cwd` is derived by replacing each `/` in the absolute path with `-`. For example, `/Users/pereid22/rose` becomes `-Users-pereid22-rose`. This encoding is lossless only for typical filesystem paths; paths containing `-` characters are not disambiguated from `/` characters by this scheme.

#### 4.1.2 Transcript Format

Each `{session_id}.jsonl` file is the full conversation transcript for that session. Every user message, assistant response, tool call, tool result, and system prompt is appended as a newline-delimited JSON object. Claude Code replays the entire file when resuming a session.

The two primary entry types are `user` and `assistant`.

**User entry:**

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

**Assistant entry:**

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

Tool results are encoded as `user` type entries with `message.content` as a JSON array rather than a plain string.

Fields used by the observability layer for session listing [R, `src/rose/api/main.py`]:

| Field | Source |
|---|---|
| `title` | `message.content` of the first `user` entry where `content` is a plain string |
| `branch` | `gitBranch` of the first `user` entry |
| `started_at` | `timestamp` of the first entry in the file |
| `ended_at` | `timestamp` of the last entry in the file, or file mtime if the final entry lacks a timestamp |

### 4.2 Session Process Registry

#### 4.2.1 `~/.claude/sessions/{pid}.json`

One file is created per running Claude Code process, keyed by the operating system process ID:

```json
{
  "pid":       71823,
  "sessionId": "dedd37bc-...",
  "cwd":       "/Users/pereid22/rose",
  "startedAt": 1775477968105
}
```

#### 4.2.2 The Resume Divergence

**Observed behaviour:** `sessionId` in `sessions/{pid}.json` represents the *process identity*, not the *transcript filename*. On a fresh session these values are identical. On a resumed session they diverge:

```
Fresh session:
  sessions/12345.json   →  sessionId: 78b85df3
  projects/.../78b85df3.jsonl  ← created; entries carry sessionId: 78b85df3  ✓ match

Resumed session:
  sessions/71823.json   →  sessionId: dedd37bc  (new process, new UUID)
  projects/.../78b85df3.jsonl  ← still being written to; entries carry sessionId: 78b85df3  ✗ diverged
  projects/.../dedd37bc.jsonl  ← never created
```

**Consequence for observability:** `sessionId` from `sessions/{pid}.json` cannot be used to locate the active transcript on a resumed session. The correct procedure is:

1. Encode `cwd` using the `/` → `-` rule to obtain the project directory name.
2. Find the `.jsonl` file in that directory whose `mtime ≥ startedAt / 1000`.
3. That file is the transcript currently being written to.

This procedure is valid because only one transcript per project directory can be modified after a given process start time. The implementation is in the rose repository [R, `src/rose/api/main.py`].

---

## 5. Agent Architecture

**Lab prerequisites:** macOS Darwin 25.2.0; Claude Code installed; rose applied (`rose install` [R]); `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS: "1"` present in `settings.json`; `teammateMode: "in-process"` present in `~/.claude.json`; active Claude API access (LLM availability required); at least one agent invocation executed. All subagent directory layouts and transcript schemas were verified by direct inspection.

### 5.1 Subagents and Teammates

Both subagents and teammates are invoked via the `Agent` tool. The distinction lies in the invocation parameters and whether bidirectional messaging is supported.

| Property | Subagent | Teammate |
|---|---|---|
| Invocation | `Agent(subagent_type, prompt)` | `Agent(subagent_type, name, team_name, prompt)` |
| Messaging | None | `SendMessage` (bidirectional) |
| Coordination | None | Team lead via `TeamCreate` |
| Storage layout | `subagents/` directory | Same `subagents/` directory |

Storage layout is identical for both; the only distinguishing signal in the transcript is the presence of `name` and `team_name` in the `Agent` tool input.

### 5.2 Process Model

**Observed behaviour:** with `teammateMode: "in-process"`, teammates are **not** separate operating system processes. This was verified by three independent observations:

1. `~/.claude/sessions/` contains exactly one file — the parent process's PID — regardless of how many teammates are active at a given moment.
2. The teammate shutdown response payload contains `"paneId": "in-process"` and `"backendType": "in-process"`.
3. In session and agent listings produced by the rose observability layer [R, `src/rose/api/main.py`], teammates appear as subagents nested under the parent session, not as top-level sessions.

**Consequence:** no teammate PIDs are available to monitoring tools. All execution occurs under the parent session's PID, and process-level isolation between teammates does not exist in this mode.

### 5.3 Agent Storage Layout

Every subagent or teammate invocation is recorded in two locations: the **parent transcript** (which records the agent as a tool call and streams its progress) and a dedicated **subagent directory** (which holds the agent's own full conversation transcript).

```
~/.claude/projects/{encoded-cwd}/
├── {session_id}.jsonl                          # parent transcript
└── {session_id}/
    ├── subagents/
    │   ├── agent-{agentId}.meta.json           # agentType + description
    │   └── agent-{agentId}.jsonl               # agent's full conversation
    └── tool-results/
```

`{agentId}` is a runtime-generated identifier (e.g. `a69d496525515eb5e`) unique to each invocation. It is not the `subagent_type` name; it is the join key between the subagent files and the parent transcript entries.

#### 5.3.1 `agent-{agentId}.meta.json`

```json
{
  "agentType": "claude-code-guide",
  "description": "Claude Code hooks reference"
}
```

- `agentType`: the named agent definition (e.g. `rose`, `claude-code-guide`, `engineer`)
- `description`: the short label passed by the invoking model at call time; distinguishes multiple invocations of the same `agentType` within a session

#### 5.3.2 `agent-{agentId}.jsonl`

The agent's full conversation transcript, in the same JSONL format as a parent session transcript. All entries carry `"isSidechain": true` and the **parent** `sessionId`.

**First entry — the prompt (`user` type):**

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

The `timestamp` of this entry is the agent's `started_at`.

**Tool call within the agent (`assistant` type):**

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

**Observed behaviour:** subagents execute on `claude-haiku-4-5-20251001` by default, not on the parent session's model. This is directly observable in the `model` field of `assistant` entries within the subagent transcript.

Fields extractable from this file for observability purposes [R, `src/rose/api/main.py`]:

| Field | Derivation |
|---|---|
| `started_at` | `timestamp` of the first entry |
| `size_kb` | File size on disk |
| `tool_use_count` | Count of `tool_use` blocks across all `assistant` entries |

**Hook progress entries (`progress` type):**

The agent's `.jsonl` also contains `progress` entries of subtype `hook_progress`. These record the agent's own hook events — for example, `PreToolUse` firing before a `WebFetch` call — and are not part of the parent-transcript join chain described in §5.4.

```json
{
  "type": "progress",
  "agentId": "a69d496525515eb5e",
  "isSidechain": true,
  "data": {
    "type": "hook_progress",
    "hookEvent": "PreToolUse",
    "hookName": "PreToolUse:WebFetch",
    "command": "~/.claude/hooks/log-session-start.sh"
  }
}
```

### 5.4 Agent Lifecycle in the Parent Transcript

Each agent invocation produces three entry categories in the **parent** `{session_id}.jsonl`, joined by a common `tool_use_id`.

#### 5.4.1 Agent Invocation (`assistant` entry)

When the model decides to invoke an agent, an `assistant` entry is appended with a `tool_use` block:

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

The `id` field is the `tool_use_id` anchor; all subsequent related entries in the parent transcript reference this value.

#### 5.4.2 Agent Execution Progress (`progress` entries)

While the agent executes, `progress` entries of subtype `agent_progress` are streamed into the parent transcript. These are distinct from the `hook_progress` entries in the agent's own `.jsonl` (§5.3.2).

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
    "prompt": "What are all the possible hooks...",
    "message": { "..." : "..." }
  }
}
```

Key properties:

- `data.type: "agent_progress"` distinguishes these from `hook_progress` entries
- `data.agentId` is the join key to `subagents/agent-{agentId}.*`
- `parentToolUseID` is the join key back to `tool_use.id` in §5.4.1
- `isSidechain: false` — these entries reside in the main conversation transcript, not the agent's sidechain
- `agentName` is absent; the human-readable agent name is available only in `.meta.json` or the `tool_use` input

There may be dozens of these entries per invocation, one per streamed response chunk.

**Critical timing gap:** `agent_progress` entries appear only once the agent begins producing output. In the window between agent start and first chunk, the `agentId → tool_use_id` link is not yet present in the parent transcript. This gap is the primary motivation for the hook-based detection approach described in §6.2.

#### 5.4.3 Agent Completion (`user` entry)

When the agent finishes, a `user` entry with a `tool_result` block is appended to the parent transcript:

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

`tool_use_id` matches `id` from §5.4.1. Agent duration is computed as `timestamp(§5.4.3) − timestamp(§5.4.1)`.

The complete timeline in the parent transcript for one agent invocation:

```
assistant  [12:06:29]  tool_use       id=toolu_01Ck  name=Agent  subagent_type=claude-code-guide
progress   [12:06:31]  agent_progress  parentToolUseID=toolu_01Ck  agentId=a69d...  (chunk 1)
progress   [12:06:33]  agent_progress  parentToolUseID=toolu_01Ck  agentId=a69d...  (chunk 2)
...
user       [12:07:15]  tool_result    tool_use_id=toolu_01Ck  ← done; duration = 46 s
```

---

## 6. Observability and Event Hooks

**Lab prerequisites:** macOS Darwin 25.2.0; Claude Code installed; rose applied (`rose install` [R]); active Claude API access (LLM availability required); hook scripts present at `~/.claude/hooks/` [R, `global/hooks/`]; at least one session with subagent invocations run after hook deployment. Log output is written to `~/.claude/logs/`.

### 6.1 Transcript Join Procedure

The observability layer [R, `src/rose/api/main.py`] reconstructs a complete picture of each agent invocation by joining data from three sources:

```
subagents/agent-{agentId}.meta.json   →  agentType, description
subagents/agent-{agentId}.jsonl       →  started_at, size_kb, tool_use_count

Parent transcript:
  progress entry  [data.agentId == agentId]        →  parentToolUseID
  user entry      [tool_result.tool_use_id == parentToolUseID]  →  agent is done
```

Procedure for each subagent:

1. Read `{agentId}` from the filename stem of `agent-*.meta.json`.
2. Read `agentType` and `description` from the meta file.
3. Read `started_at`, `size_kb`, and `tool_use_count` from `agent-{agentId}.jsonl`.
4. Scan parent transcript `progress` entries where `data.agentId == agentId` to obtain `parentToolUseID`.
5. Scan parent transcript `user` entries for a `tool_result` where `tool_use_id == parentToolUseID`.
6. A matching `tool_result` indicates the agent is **done**; its absence in a live session indicates the agent is **live**.

### 6.2 SubagentStart and SubagentStop Hook Payloads

Claude Code fires two hook events around every subagent invocation: `SubagentStart` and `SubagentStop`. These provide an authoritative, real-time signal independent of the transcript join and immune to the timing gap in §5.4.2.

Hook registration in `settings.json` [R, `global/settings.json`]:

```json
"SubagentStart": [{ "type": "command", "command": "~/.claude/hooks/log-subagent-events.sh" }],
"SubagentStop":  [{ "type": "command", "command": "~/.claude/hooks/log-subagent-events.sh" }]
```

Both events are handled by the same script, which writes to `~/.claude/logs/subagent-events.jsonl`.

#### 6.2.1 SubagentStart Payload

Fires at the moment the subagent begins. The subagent's own transcript file may not yet exist on disk at this point.

```json
{
  "session_id": "78b85df3-9ce0-4d1d-a4ce-2d7459980b92",
  "transcript_path": "/Users/pereid22/.claude/projects/-Users-pereid22-rose/78b85df3-....jsonl",
  "cwd": "/Users/pereid22/rose",
  "agent_id": "a73f163bf6391f728",
  "agent_type": "rose-backlog",
  "hook_event_name": "SubagentStart"
}
```

`transcript_path` references the **parent** session transcript, not the agent's own `.jsonl`.

#### 6.2.2 SubagentStop Payload

Fires when the subagent finishes normally. Adds the agent transcript path and the agent's final assistant message.

```json
{
  "session_id": "78b85df3-9ce0-4d1d-a4ce-2d7459980b92",
  "agent_id": "a73f163bf6391f728",
  "agent_type": "rose-backlog",
  "hook_event_name": "SubagentStop",
  "stop_hook_active": false,
  "agent_transcript_path": "/Users/pereid22/.claude/projects/-Users-pereid22-rose/78b85df3-.../subagents/agent-a73f163bf6391f728.jsonl",
  "last_assistant_message": "Task complete. Read one file, reported back to team-lead."
}
```

Field reference:

| Field | SubagentStart | SubagentStop | Notes |
|---|---|---|---|
| `session_id` | ✓ | ✓ | Parent session UUID |
| `agent_id` | ✓ | ✓ | Join key to `subagents/agent-{agentId}.*` |
| `agent_type` | ✓ | ✓ | Named agent type |
| `hook_event_name` | ✓ | ✓ | `"SubagentStart"` or `"SubagentStop"` |
| `transcript_path` | ✓ | — | Parent transcript path |
| `agent_transcript_path` | — | ✓ | Agent's own `.jsonl` path |
| `last_assistant_message` | — | ✓ | Final response text from the agent |
| `stop_hook_active` | — | ✓ | Whether a `Stop` hook is also firing concurrently |

### 6.3 PostToolUse:SendMessage Hook

`SendMessage` is a tool call subject to `PreToolUse` and `PostToolUse` hooks. Intercepting it provides a completion signal for agents terminated via the teammate messaging protocol — a case not covered by `SubagentStop` (§6.4.3, case 3).

Hook registration in `settings.json` [R, `global/settings.json`]:

```json
"PostToolUse": [
  {
    "matcher": "SendMessage",
    "hooks": [
      {
        "type": "command",
        "command": "HOOK_EVENT=PostToolUse:SendMessage ~/.claude/hooks/log-message-events.sh"
      }
    ]
  }
]
```

Writes to `~/.claude/logs/message-events.jsonl`. Implementation: [R, `global/hooks/log-message-events.sh`].

**Payload:**

```json
{
  "session_id": "78b85df3-9ce0-4d1d-a4ce-2d7459980b92",
  "transcript_path": "...",
  "cwd": "/Users/pereid22/rose",
  "hook_event_name": "PostToolUse",
  "tool_name": "SendMessage",
  "tool_input": {
    "to": "rose-backlog",
    "message": { "type": "shutdown_request" },
    "summary": "Shut down rose-backlog"
  },
  "tool_response": {
    "success": true,
    "request_id": "shutdown-...@rose-backlog",
    "target": "rose-backlog"
  },
  "tool_use_id": "toolu_vrtx_01..."
}
```

Key fields:

| Field | Notes |
|---|---|
| `tool_input.to` | Recipient agent name |
| `tool_input.message.type` | `"shutdown_request"`, `"shutdown_response"`, `"plan_approval_response"`, or absent for plain text messages |
| `tool_response.success` | Whether the message was delivered |

**Scope:** this hook fires for all `SendMessage` calls in the session — from the team lead and from all in-process teammates. The originating agent is not identified in the payload; it must be inferred from context (for example, `tool_input.to` being the team lead implies the message originated from a teammate).

### 6.4 Live/Done Detection

Three signal tiers, in decreasing order of reliability:

#### 6.4.1 Tier 1 — Hook Log (Authoritative)

Read `~/.claude/logs/subagent-events.jsonl` sequentially, retaining the last event per `agent_id`:

```
SubagentStart  →  live
SubagentStop   →  done
```

`agent_id` matches the filename stem of `subagents/agent-{agentId}.jsonl`; no transcript join needed. Accurate from the first millisecond of the agent's existence.

#### 6.4.2 Tier 2 — Transcript Tool-Result Join (Slight Timing Gap)

Fallback for sessions predating hook deployment (procedure in §6.1):

```
agent_progress entry present  →  parentToolUseID known
tool_result entry present     →  done
```

`agent_progress` entries are absent between `SubagentStart` and first chunk (§5.4.2), causing a transient join failure. This gap motivated Tier 1.

#### 6.4.3 Known Cases Where SubagentStop Does Not Fire

`SubagentStop` is absent in three confirmed cases:

1. **Abrupt process exit.** The parent Claude Code process is killed or crashes before the hook can execute.
2. **Context window exhaustion.** The context limit is reached while the agent is mid-execution.
3. **Messaging protocol shutdown.** When the agent exits via the `shutdown_request` / `shutdown_approved` handshake (§6.3), Claude Code does not treat this as a natural subagent lifecycle end; `SubagentStop` does not fire.

The transcript tool-result join (Tier 2) is immune to cases 1 and 2, as `tool_result` entries are written by Claude Code directly into the parent transcript before the process exits. For case 3, neither the hook log nor the transcript provides a completion signal; the `SendMessage` hook (§6.3) must be consulted instead.

#### 6.4.4 Orphaned Agents

A fourth failure mode exists: the agent starts, but the context limit is reached before any `agent_progress` entry is written into the parent transcript. The result is an orphaned `SubagentStart` in the hook log with no corresponding `agent_progress`, no `tool_result`, and a subagent `.jsonl` whose last `assistant` entry carries `stop_reason: null`.

In this case, the agent's `.jsonl` mtime is the definitive signal. A live agent writes to its file continuously — each tool call and each response chunk produces a write. If the file mtime has not advanced in more than 120 seconds, the agent is treated as gone regardless of what the hook log indicates.

#### 6.4.5 Decision Procedure

```
SubagentStop fired for this agent_id?
├─ yes → done                                           (Tier 1 — definitive)
└─ no  → tool_result present in parent transcript?
          ├─ yes → done                                 (Tier 2 — SubagentStop missed)
          └─ no  → shutdown_request sent to this agent_type after it started?
                    ├─ yes → done                       (messaging shutdown — §6.4.3 case 3)
                    └─ no  → SubagentStart fired?
                              ├─ yes → agent .jsonl silent for > 120 s?
                              │         ├─ yes → done   (orphaned — §6.4.4)
                              │         └─ no  → live
                              └─ no  → done             (no signal — conservative default)
```

After computing live/done status, a final clamp is applied: an agent assessed as live within a session assessed as dead is reclassified as done.

The shutdown signal is read from `~/.claude/logs/message-events.jsonl` (§6.3). The correlation key is `tool_input.to` matched against the agent's `agent_type`, gated by `started_at` to avoid incorrectly classifying prior invocations of the same agent type as done.

---

## 7. Memory System

**Lab prerequisites:** macOS Darwin 25.2.0; Claude Code installed; rose applied (`rose install` [R]); active Claude API access (LLM availability required). The memory system is configured via [R, `global/CLAUDE.md`].

Claude Code supports a file-based memory system. The index is loaded automatically into every session's system prompt.

### 7.1 Storage Layout

```
~/.claude/projects/{encoded-cwd}/memory/
├── MEMORY.md      ← index file; loaded into every conversation
└── {name}.md      ← individual memory entries
```

`MEMORY.md` is the index. It must remain concise — content beyond approximately 200 lines is truncated and will not appear in context — and must contain only pointers to individual memory files, never memory content directly.

### 7.2 Memory Types

| Type | Purpose |
|---|---|
| `user` | User identity — role, expertise, communication preferences |
| `feedback` | Corrections and confirmed approaches: behaviours to avoid, behaviours to repeat |
| `project` | Ongoing context, goals, design decisions, deadlines |
| `reference` | Pointers to non-obvious external facts that would otherwise require rediscovery |

### 7.3 Entry Format

Each memory file uses YAML frontmatter:

```markdown
---
name: SubagentStop reliability
description: SubagentStop does not fire on abrupt exit or context limit
type: reference
---

Content. For feedback and project types, structure as: rule or fact, then a **Why:** line
(the reason — often a past incident or constraint) and a **How to apply:** line (when
this guidance is relevant). The Why line permits correct application to edge cases.
```

### 7.4 Scope

**Save:** non-obvious, durable facts — behavioural findings, confirmed decisions, user preferences, external resource locations.

**Do not save:** facts derivable from code or git history (file paths, architecture, recent changes), in-progress work, or anything already in `CLAUDE.md` files. Such entries become stale and degrade system reliability.

---

## Sources

[1] Anthropic. *Claude Code Documentation*. https://docs.anthropic.com/en/docs/claude-code

[2] openclaw. *OpenClaw — Personal AI Assistant Platform*. GitHub. https://github.com/openclaw/openclaw

[3] gastownhall. *Gastown — Multi-Agent AI Orchestration System*. GitHub. https://github.com/gastownhall/gastown

[4] MyClaw. *Managed OpenClaw Hosting*. https://myclaw.ai/

[5] LangChain. *LangGraph Documentation*. https://langchain-ai.github.io/langgraph/

[6] LangChain. *LangChain Documentation*. https://python.langchain.com/

[7] CrewAI. *CrewAI Documentation*. https://docs.crewai.com/

[8] Microsoft. *AutoGen*. https://microsoft.github.io/autogen/

[9] Microsoft. *Semantic Kernel Documentation*. https://learn.microsoft.com/en-us/semantic-kernel/

[10] Amazon Web Services. *Amazon Bedrock Agents*. https://aws.amazon.com/bedrock/agents/

[11] Google Cloud. *Vertex AI Agents*. https://cloud.google.com/vertex-ai/docs/agents/overview

[12] OpenAI. *Assistants API*. https://platform.openai.com/docs/assistants/overview

[13] deepset. *Haystack*. https://haystack.deepset.ai/

[R] diogobaltazar. *rose — Claude Code Configuration and Observability*. GitHub. https://github.com/diogobaltazar/rose
