#!/usr/bin/env bash
# Bound to PostToolUse in settings.json.
# Claude Code passes a JSON payload on stdin:
#   { "tool_name": "Bash", "tool_input": {...}, "tool_response": {...} }
#
# Appends a tool.call event to ~/.claude/logs/<session-id>/events.jsonl.

set -euo pipefail

SESSION_ID="${CLAUDE_SESSION_ID:-unknown}"
LOG_DIR="${HOME}/.claude/logs/${SESSION_ID}"
EVENTS_FILE="${LOG_DIR}/events.jsonl"

mkdir -p "$LOG_DIR"

# Read the full stdin payload once.
PAYLOAD=$(cat)

TOOL_NAME=$(echo "$PAYLOAD" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_name','unknown'))" 2>/dev/null || echo "unknown")

# Truncate tool_input to 500 chars to keep logs lean.
TOOL_INPUT=$(echo "$PAYLOAD" | python3 -c "
import sys, json
d = json.load(sys.stdin)
raw = json.dumps(d.get('tool_input', {}))
print(raw[:500] + ('...' if len(raw) > 500 else ''))
" 2>/dev/null || echo "{}")

TS=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")
SEQ=$(( $(wc -l < "$EVENTS_FILE" 2>/dev/null || echo 0) + 1 ))

printf '%s\n' "{\"ts\":\"${TS}\",\"session_id\":\"${SESSION_ID}\",\"seq\":${SEQ},\"source\":\"hook\",\"agent\":null,\"step\":null,\"event\":\"tool.call\",\"payload\":{\"tool\":\"${TOOL_NAME}\",\"input\":${TOOL_INPUT}}}" \
  >> "$EVENTS_FILE"
