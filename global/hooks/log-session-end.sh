#!/usr/bin/env bash
# Bound to Stop in settings.json.
# Fires when Claude Code stops (session ends or is interrupted).
#
# Reads the final step.exit event from events.jsonl to determine outcome,
# then updates meta.json with ended_at, status, and outcome.

set -euo pipefail

SESSION_ID="${CLAUDE_SESSION_ID:-unknown}"
LOG_DIR="${HOME}/.claude/logs/${SESSION_ID}"
EVENTS_FILE="${LOG_DIR}/events.jsonl"
META_FILE="${LOG_DIR}/meta.json"

mkdir -p "$LOG_DIR"

TS=$(date -u +"%Y-%m-%dT%H:%M:%S.000Z")

# Derive outcome from the last step.exit event, if any.
OUTCOME="abandoned"
if [[ -f "$EVENTS_FILE" ]]; then
  LAST_STEP=$(grep '"event":"step.exit"' "$EVENTS_FILE" | tail -1 | \
    python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('step',''))" 2>/dev/null || echo "")

  case "$LAST_STEP" in
    P2)   OUTCOME="delivery" ;;
    W1)   OUTCOME="investigation" ;;
    "")   OUTCOME="abandoned" ;;
    *)    OUTCOME="in_progress" ;;
  esac
fi

# Append session.end event.
SEQ=$(( $(wc -l < "$EVENTS_FILE" 2>/dev/null || echo 0) + 1 ))
printf '%s\n' "{\"ts\":\"${TS}\",\"session_id\":\"${SESSION_ID}\",\"seq\":${SEQ},\"source\":\"hook\",\"agent\":null,\"step\":null,\"event\":\"session.end\",\"payload\":{\"outcome\":\"${OUTCOME}\",\"final_step\":\"${LAST_STEP:-null}\"}}" \
  >> "$EVENTS_FILE"

# Update meta.json.
if [[ -f "$META_FILE" ]]; then
  python3 -c "
import sys, json
with open('${META_FILE}') as f:
    meta = json.load(f)
meta['ended_at'] = '${TS}'
meta['status'] = 'completed'
meta['outcome'] = '${OUTCOME}'
with open('${META_FILE}', 'w') as f:
    json.dump(meta, f, indent=2)
" 2>/dev/null || true
else
  # meta.json missing — write a minimal one.
  printf '%s\n' "{\"session_id\":\"${SESSION_ID}\",\"ended_at\":\"${TS}\",\"status\":\"completed\",\"outcome\":\"${OUTCOME}\"}" \
    > "$META_FILE"
fi
