# Topgun Architecture — Target State

## Overview

Topgun is a **multi-tenant SaaS** autonomous development system:
- **AMC Victoria** — webapp (landing + command deck)
- **Topgun API** — FastAPI backend on Hetzner; reads/writes all user data via the Google Drive API
- **Topgun CLI** — Python CLI, authenticates against the API
- **ONA environments** — remote Claude Code instances; write logs directly to Google Drive
- **Maverick mode** — local Claude Code with same capabilities as ONA
- **Google Drive** — source of truth for all user data (`registry.jsonl`, `timers.jsonl`, `config.json`, `sessions/`, `vault/`)
- **Topgun daemon** — sole job: copies local `~/.claude` logs to Google Drive `topgun/sessions/`

---

## 1. Multi-Tenant Architecture

Many users share one backend. The backend reads/writes user data from Google Drive on every request. No user data stored in the backend beyond encrypted credentials.

### What lives where

| Store | Contents |
|-------|----------|
| **Backend DB** (Redis) | Encrypted Google Drive refresh token per user; encrypted service tokens (GitHub, CalDAV) |
| **Google Drive** `topgun/` | Everything: `registry.jsonl`, `timers.jsonl`, `config.json`, `sessions/`, `vault/` |
| **Sources** (GitHub, Obsidian) | Document content and tags — never stored by topgun |

### Encryption model

```
encryption_key = HMAC(BACKEND_SECRET, auth0_sub)
```

- `BACKEND_SECRET` — env var on Hetzner, never leaves the server
- `auth0_sub` — stable per-user identifier from Auth0 JWT
- Used to encrypt service tokens stored in backend DB

### CLI Installation

The topgun CLI is a native Python package. Install via `uv`:

```bash
# Install uv (once)
brew install uv
# or: curl -LsSf https://astral.sh/uv/install.sh | sh

# Install topgun CLI
uv tool install /path/to/topgun

# Upgrade after code changes
uv tool upgrade topgun
```

For local development, install in editable mode:
```bash
uv tool install --editable /path/to/topgun
```

### Local development stack

Only the backend and webapp run in Docker:

```bash
docker compose --env-file .env up api web
```

### Bootstrap sequence (once per user)

```bash
topgun auth login                                            # 1. Auth0 device flow
topgun config set backend icloud                             # 2. declare iCloud as storage
topgun config set github --name personal-github \
  --account d.obaltazar@gmail.com \
  --repos diogobaltazar/topgun                              # 3. declare connection
topgun auth login --name personal-github                     # 4. GitHub OAuth
topgun daemon start                                          # 5. log sync daemon
```

1. Auth0 token → `~/.config/topgun/auth.json`
2. Writes `"storage": {"provider": "icloud"}` to `iCloud/topgun/config.json`
3. Adds connection to `iCloud/topgun/config.json`
4. GitHub OAuth → refresh token encrypted → stored in backend DB (keyed by auth0_sub + name)
5. Daemon watches `~/.claude` → copies session logs to `iCloud/topgun/sessions/`

---

## 2. iCloud Drive Layout

```
iCloud Drive/topgun/
├── registry.jsonl       # Intel document registry (one line per tracked document)
├── timers.jsonl         # Timer events (one line per start/stop)
├── config.json          # Connections + storage config (human-readable)
├── credentials.enc      # Encrypted service tokens (fallback; primary in backend DB)
├── sessions/            # Claude Code logs from ALL instances (local + ONA)
│   ├── {session_id}.jsonl
│   └── ...
└── vault/               # Obsidian vault — edit directly in Obsidian
    └── *.md
```

### `registry.jsonl`

```jsonl
{"uid": "abc123", "source": "github", "source_url": "https://github.com/owner/repo/issues/1"}
{"uid": "def456", "source": "obsidian", "source_url": "topgun/vault/2026-05-04-rate-limiting/task.md"}
```

### `timers.jsonl`

```jsonl
{"uid": "abc123", "event": "start", "ts": "2026-05-04T02:00:00Z"}
{"uid": "abc123", "event": "stop",  "ts": "2026-05-04T02:30:00Z"}
{"uid": "def456", "event": "start", "ts": "2026-05-04T03:15:00Z"}
```

### `config.json`

Connections own their resources — no separate `sources` array:

```json
{
  "storage": {
    "provider": "icloud",
    "vault": "topgun/vault"
  },
  "connections": {
    "personal-github": {
      "provider": "github",
      "account": "d.obaltazar@gmail.com",
      "repos": ["diogobaltazar/topgun"]
    },
    "roche-github": {
      "provider": "github",
      "account": "diogo.pereira-marques@roche.com",
      "repos": ["roche-org/project"]
    },
    "apple-calendar": {
      "provider": "caldav",
      "account": "apple.diogo@fastmail.com"
    }
  }
}
```

Tags and content never stored here — they live at source (GitHub labels, Obsidian frontmatter).

---

## 3. Topgun Daemon

Single responsibility: copy local `~/.claude` session logs to `Google Drive/topgun/sessions/`.

```bash
topgun daemon start    # watches ~/.claude, copies new/updated sessions to Google Drive
topgun daemon stop
topgun daemon status
```

- Runs as a background process on the user's Mac
- ONA environments write their logs directly to Google Drive
- Backend reads sessions from Google Drive for observability

---

## 4. Connections Registry

Each connection declares its own resources. Adding a repo = adding it under the right connection in `config.json`.

```
topgun config set github --name personal-github \
  --account d.obaltazar@gmail.com \
  --repos diogobaltazar/topgun

topgun config set github --name roche-github \
  --account diogo.pereira-marques@roche.com \
  --repos roche-org/project

topgun config set caldav --name apple-calendar \
  --account apple.diogo@fastmail.com

topgun config list
topgun config remove --name roche-github
```

---

## 5. Webapp: AMC Victoria

Single webapp (`docker compose up web`).

### Routes

| Route | Component | Description |
|-------|-----------|-------------|
| `/` | Landing | Hero page |
| `/callback` | Callback | Auth0 redirect |
| `/deck` | CommandDeck | Authenticated mission control |
| `/deck/connections` | Connections | Manage connected accounts |

### Command Deck Tabs

| Tab | Content |
|-----|---------|
| **Missions** | Intel tagged `topgun-mission` at source |
| **Intel** | All registered intel regardless of tags |

### Default View: Stats Dashboard

Backend reads `registry.jsonl` from iCloud → fetches tags from sources → computes:
- Total intel documents
- Missions (tagged `topgun-mission`), drafts, ready
- By source (GitHub vs Obsidian)

Hybrid cache: backend caches stats with short TTL, refreshes on page load.

### Card View (opt-in)

Per-card fetching: GitHub via GitHub API, Obsidian via iCloud vault file.
Clicking a card: GitHub URL in new tab, Obsidian deep-link (`obsidian://`).

### Search

Scoped to registered UIDs in `registry.jsonl`. Backend fetches content from sources and matches on title + body.

### Conversational Actions (xterm.js terminal)

| Skill | Webapp trigger | CLI |
|-------|---------------|-----|
| `/topgun-create-intel` | "Create Intel" | `topgun intel create` |
| `/topgun-create-mission` | "Create Mission" | `topgun mission create` |
| `/topgun-mission-plan` | "Plan" | `topgun mission plan <uid>` |

Webapp: embedded xterm.js → ONA environment.
CLI default: SSH into ONA.
CLI `--maverick`: local Claude Code.

---

## 6. CLI Authentication

```
topgun auth login                       # Auth0 device flow (like gh auth login)
topgun auth login --name <connection>   # OAuth for a declared service
topgun auth logout
topgun auth logout --name <connection>
topgun auth status
```

### Config commands

```
topgun config set backend icloud
topgun config set github --name <n> --account <email> --repos <repo,...>
topgun config set caldav  --name <n> --account <email>
topgun config list
topgun config remove --name <n>
```

---

## 7. Intel Documents

### `registry.jsonl` entries

```jsonl
{"uid": "abc123", "source": "github",   "source_url": "https://github.com/owner/repo/issues/1"}
{"uid": "def456", "source": "obsidian", "source_url": "topgun/vault/2026-05-04-note/task.md"}
```

### Registration paths

**Fresh creation** (conversational):
```
UID generated → conversation with agent → save →
  agent appends line to registry.jsonl in iCloud
```

**Track existing**:
- GitHub issue: append line to `registry.jsonl` pointing to the issue URL
- Obsidian file (must be within configured vault): agent generates topgun-format wrapper file, appends line pointing to wrapper

### Manual time tracking

Events appended to `timers.jsonl`. Total = sum of completed intervals + live elapsed if running.

### Tags (live at source, never in topgun files)

- `topgun-mission` — appears in Missions tab
- `topgun-mission-draft` — no plan yet
- `topgun-mission-ready` — plan generated and approved

---

## 8. Missions

Intel document with `topgun-mission` tag at source.

```
[create] → tagged topgun-mission-draft at source
    ↓
[plan] → HITL conversational planning
    ↓
[approved] → tag upgraded to topgun-mission-ready
    ↓
[engage] → autonomous pilot fleet execution
```

### Mission Planning (`/topgun-mission-plan`)

1. Reads `registry.jsonl` → fetches related intel from sources
2. Interviews user — walks design branches, resolves dependencies
3. Explores codebase autonomously
4. Dispatches pilot subagents for research
5. Optionally generates Gemini Deep Research prompt
6. Produces: GitHub sub-issues + Obsidian tasks (each appended to `registry.jsonl`)
7. On approval: upgrades tag at source

---

## 9. ONA Environments

At startup, backend:
1. Derives `encryption_key = HMAC(BACKEND_SECRET, auth0_sub)`
2. Decrypts service tokens from backend DB
3. Injects refresh tokens into ONA environment

ONA writes session logs directly to `Google Drive/topgun/sessions/`. ONA contacts OAuth providers directly for token refresh — no backend callback needed.

---

## 10. CLI Parity

| Webapp | CLI |
|--------|-----|
| Login | `topgun auth login` |
| Connect service | `topgun config set github --name <n>` + `topgun auth login --name <n>` |
| Connections page | `topgun config list` |
| Create Intel | `topgun intel create` |
| Track existing | `topgun intel track <url-or-path>` |
| Intel tab | `topgun intel list` |
| Search | `topgun intel search <query>` |
| Create Mission | `topgun mission create` |
| Missions tab | `topgun mission list` |
| Plan mission | `topgun mission plan <uid>` |
| Engage mission | `topgun mission engage <uid>` |
| Watch missions | `topgun mission watch` |

`--maverick` flag: default = API/ONA, `--maverick` = local.

---

## 11. Backend API

Backend reads all user data from iCloud via the iCloud API. Auth0 JWT on every request.

```
GET    /config                         # Auth0 app config (public)

# Connections
POST   /connect/service                # Store encrypted service token (backend DB)
GET    /connect                        # List connections
DELETE /connect/{name}                 # Remove connection

# Intel (reads registry.jsonl from iCloud)
GET    /intel                          # List all registered intel
GET    /intel/{uid}                    # Get entry + fetch content from source
POST   /intel                          # Append to registry.jsonl in iCloud
DELETE /intel/{uid}                    # Remove from registry.jsonl

# Intel search + stats
GET    /intel/search?q=<query>
GET    /intel/stats

# Timer (reads/writes timers.jsonl in iCloud)
GET    /timer/{uid}
POST   /timer/{uid}/start
POST   /timer/{uid}/stop

# Config (reads/writes config.json in iCloud)
GET    /config/user
PATCH  /config/user

# Sessions / Observability (reads sessions/ from iCloud)
GET    /sessions
WebSocket /ws
```

### Backend DB (Redis) — per user

```
creds:{auth0_sub}:{connection_name}  →  encrypted refresh token
```

Nothing else. All user data lives in iCloud.

---

## 12. Data Flow

```
Obsidian ──(sync TBD)──▶ Google Drive/topgun/
                          ├── registry.jsonl
                          ├── timers.jsonl    ◀──┐
                          ├── config.json        │  Backend reads/writes
                          ├── sessions/       ◀──┤  via Google Drive API
                          │   ├── ONA logs       │
                          │   └── local logs  ◀──┘
                          └── vault/*.md

                          Backend (Hetzner)
                          ├── reads/writes Google Drive API
                          ├── DB: encrypted GDrive + service tokens
                          └── serves Webapp + CLI

ONA env  ──logs──▶ Google Drive sessions/
         ──auth──▶ GitHub / CalDAV (directly, refresh tokens injected at start)

Daemon   ──copies──▶ ~/.claude → Google Drive sessions/
```

---

## 13. Implementation Phases

### Phase 1: Intel Foundation ✓
- API: `/intel` CRUD + search + stats (Redis interim storage)
- CLI: `topgun intel list`, `topgun intel track`, `topgun intel search`
- Webapp: Command Deck, Intel/Missions tabs, stats, card view

### Phase 2: Auth + Connections + Google Drive ✓
- `topgun auth login/logout/status`
- `topgun config set/list/remove`
- Backend: Google Drive client, connections endpoints, encrypted credential storage
- `registry.jsonl`, `timers.jsonl`, `config.json` read/write via Google Drive API
- Webapp: `/deck/connections` page

### Phase 3: Topgun Daemon
- `topgun daemon start/stop/status`
- Watches `~/.claude` → copies to `Google Drive/topgun/sessions/`

### Phase 4: Conversational Creation
- `/topgun-create-intel`, `/topgun-create-mission` skills
- ONA integration (xterm.js + SSH)
- ONA writes logs directly to Google Drive

### Phase 5: Mission Planning
- `/topgun-mission-plan` skill
- Sub-issues appended to `registry.jsonl`
- Gemini Deep Research integration

### Phase 6: Observability
- Backend reads `sessions/` from Google Drive
- Real-time mission watch via WebSocket

---

## 14. GCP Setup — Google Drive OAuth2

One GCP project per topgun deployment (not per user). Users authenticate with their own Google accounts via your OAuth2 client.

### Step 1 — Create a GCP project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click **Select a project** → **New Project**
3. Name it `topgun` (or similar), click **Create**

### Step 2 — Enable the Google Drive API

1. In your project, go to **APIs & Services** → **Library**
2. Search for `Google Drive API`
3. Click it → **Enable**

### Step 3 — Configure the OAuth consent screen

1. Go to **APIs & Services** → **OAuth consent screen**
2. Choose **External** (allows any Google account to connect)
3. Fill in:
   - App name: `Topgun`
   - User support email: your email
   - Developer contact email: your email
4. Click **Save and Continue** through Scopes (add nothing here)
5. On **Test users**: add your own Google account while in development
6. Submit

> **Note:** While the app is in "Testing" mode only test users can connect.
> To allow any user, you must publish the app (requires Google verification for sensitive scopes).
> `drive.file` scope is **not** sensitive — it only accesses files the app itself creates,
> so verification is not required.

### Step 4 — Create OAuth2 credentials

1. Go to **APIs & Services** → **Credentials**
2. Click **+ Create Credentials** → **OAuth client ID**
3. Application type: **Web application**
4. Name: `topgun-backend`
5. Under **Authorised redirect URIs**, add:
   - `http://localhost:5101/connect/backend/callback` (local dev)
   - `https://api.tgun.dev/connect/backend/callback` (production, when you have a domain)
6. Click **Create**
7. Copy the **Client ID** and **Client Secret**

### Auth0 — Two applications

The webapp and CLI use separate Auth0 applications:

| App | Type | Grant Types |
|-----|------|-------------|
| `topgun-web` (SPA) | Single Page Application | Authorization Code, Implicit |
| `topgun-cli` (Native) | Native | Authorization Code, Device Code, Refresh Token |

Create both in Auth0 → Applications → Create Application.

### Step 5 — Set env vars (backend only)

The backend only needs the redirect URI and a secret. Client credentials are provided by each user via the CLI — no shared GCP app on the server.

```bash
# In your .env file
AUTH0_CLI_CLIENT_ID=    # Native app client ID (Device Code flow)
GDRIVE_REDIRECT_URI=http://localhost:5101/connect/backend/callback
BACKEND_SECRET=a-long-random-string-change-this
```

Generate a strong `BACKEND_SECRET`:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Step 6 — First user connection

```bash
topgun auth login                           # Auth0 device flow
topgun config set backend gdrive \
  --client-id xxx.apps.googleusercontent.com \
  --client-secret xxxx                      # your GCP OAuth credentials
topgun auth login backend                   # opens browser → Google OAuth → backend stores token
```

After step 3, Google Drive is connected. Your `topgun/` folder is created automatically on first write.

### Scope used

`https://www.googleapis.com/auth/drive.file` — access only files created by the topgun app. Users see these in Google Drive under **Computers** → **topgun**. topgun cannot read any other Drive files.
