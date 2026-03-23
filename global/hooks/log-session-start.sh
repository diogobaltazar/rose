#!/usr/bin/env bash
# Bound to PreToolUse on the very first tool call of a session (via a sentinel file).
# Writes meta.json and the opening session.start event to events.jsonl.
#
# Because Claude Code has no dedicated "session open" hook, we fire once on the
# first PreToolUse by checking for the absence of meta.json.

set -euo pipefail

SESSION_ID="${CLAUDE_SESSION_ID:-unknown}"
LOG_DIR="${HOME}/.claude/logs/${SESSION_ID}"
META_FILE="${LOG_DIR}/meta.json"
EVENTS_FILE="${LOG_DIR}/events.jsonl"

# Only run once per session.
[[ -f "$META_FILE" ]] && exit 0

mkdir -p "$LOG_DIR"

TS=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")

# Use --git-common-dir so worktrees resolve to the main repo root, not the worktree path.
REPO=$(dirname "$(git -C "${CLAUDE_PROJECT_DIR:-$(pwd)}" rev-parse --absolute-git-dir 2>/dev/null | sed 's|/worktrees/[^/]*$||')" 2>/dev/null || echo "unknown")
BRANCH=$(git -C "${CLAUDE_PROJECT_DIR:-$(pwd)}" rev-parse --abbrev-ref HEAD 2>/dev/null || echo "unknown")
ISSUE=$(echo "$BRANCH" | grep -oE 'feat/([0-9]+)-' | grep -oE '[0-9]+' || echo "null")

# Write meta.json.
cat > "$META_FILE" <<EOF
{
  "session_id": "${SESSION_ID}",
  "started_at": "${TS}",
  "status": "in_progress",
  "outcome": null,
  "repository": "${REPO}",
  "branch": "${BRANCH}",
  "issue": "${ISSUE}"
}
EOF

# Write session.start event.
printf '%s\n' "{\"ts\":\"${TS}\",\"session_id\":\"${SESSION_ID}\",\"seq\":1,\"source\":\"hook\",\"agent\":null,\"step\":null,\"event\":\"session.start\",\"payload\":{}}" \
  >> "$EVENTS_FILE"
