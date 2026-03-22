#!/usr/bin/env bash
# Post-write validation hook — runs after Write/Edit tool calls
# Fast per-file checks only; heavy validation happens at Stop time.
# Exit 0: pass silently. Exit 2: feed errors back to Claude.

set -euo pipefail

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get('tool_input', {}).get('file_path', ''))
except:
    print('')
" 2>/dev/null)

[ -z "$FILE_PATH" ] && exit 0
[ ! -f "$FILE_PATH" ] && exit 0

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(pwd)}"
EXT="${FILE_PATH##*.}"
ERRORS=""

# ── TypeScript / JavaScript ──────────────────────────────────────────────────
if [[ "$EXT" =~ ^(ts|tsx|mts)$ ]] || [[ "$EXT" =~ ^(js|jsx|mjs)$ ]]; then

  # Biome (fast, zero-config)
  if command -v biome &>/dev/null && [ -f "$PROJECT_DIR/biome.json" ]; then
    OUT=$(biome check "$FILE_PATH" 2>&1) || ERRORS+="Biome:\n$OUT\n"

  # ESLint fallback
  elif command -v npx &>/dev/null && \
       ls "$PROJECT_DIR"/.eslintrc* "$PROJECT_DIR"/eslint.config* 2>/dev/null | head -1 &>/dev/null; then
    OUT=$(cd "$PROJECT_DIR" && npx eslint --max-warnings 0 "$FILE_PATH" 2>&1) || ERRORS+="ESLint:\n$OUT\n"
  fi
fi

# ── Python ───────────────────────────────────────────────────────────────────
if [[ "$EXT" == "py" ]]; then
  if command -v ruff &>/dev/null; then
    OUT=$(ruff check "$FILE_PATH" 2>&1) || ERRORS+="Ruff:\n$OUT\n"
  fi
fi

# ── Rust ─────────────────────────────────────────────────────────────────────
if [[ "$EXT" == "rs" ]] && command -v rustfmt &>/dev/null; then
  OUT=$(rustfmt --check "$FILE_PATH" 2>&1) || ERRORS+="rustfmt:\n$OUT\n"
fi

# ── Go ───────────────────────────────────────────────────────────────────────
if [[ "$EXT" == "go" ]] && command -v gofmt &>/dev/null; then
  DIFF=$(gofmt -l "$FILE_PATH")
  [ -n "$DIFF" ] && ERRORS+="gofmt: $FILE_PATH needs formatting\n"
fi

if [ -n "$ERRORS" ]; then
  printf "⚠ Validation errors in %s — fix before continuing:\n\n%b" "$FILE_PATH" "$ERRORS" >&2
  exit 2
fi

exit 0
