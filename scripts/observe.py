#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rose-observe — ASCII flow diagram from events.jsonl

Usage:
  python scripts/observe.py                 # reads active session
  python scripts/observe.py <session-id>    # reads specific session
  python scripts/observe.py --list          # list all sessions
"""

import json
import sys
from pathlib import Path
from datetime import datetime, timezone

LOGS_DIR = Path.home() / ".claude" / "logs"

ACTORS = [
    {"id": "user",          "label": "USER",    "col": 0},
    {"id": "rose",          "label": "ROSE",    "col": 1},
    {"id": "rose-research", "label": "RESEARCH","col": 2},
    {"id": "rose-backlog",  "label": "BACKLOG", "col": 3},
]
ACTOR_IDX = {a["id"]: i for i, a in enumerate(ACTORS)}

NODES = ["FP", "AF", "DR", "BI", "CONV"]


# ── data loading ─────────────────────────────────────────────────────────────

def load_session(session_id):
    log_dir = LOGS_DIR / session_id
    events = []
    if (log_dir / "events.jsonl").exists():
        with open(log_dir / "events.jsonl") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    meta = {}
    if (log_dir / "meta.json").exists():
        with open(log_dir / "meta.json") as f:
            try:
                meta = json.load(f)
            except json.JSONDecodeError:
                pass
    return events, meta


def resolve_session():
    if len(sys.argv) > 1 and sys.argv[1] == "--list":
        list_sessions()
        sys.exit(0)
    if len(sys.argv) > 1:
        return sys.argv[1]
    active = LOGS_DIR / ".active-session"
    if active.exists():
        return active.read_text().strip()
    # Fall back to most recent session by mtime
    dirs = sorted(
        [d for d in LOGS_DIR.iterdir() if d.is_dir()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    if dirs:
        return dirs[0].name
    print("No sessions found in ~/.claude/logs/", file=sys.stderr)
    sys.exit(1)


def list_sessions():
    dirs = sorted(
        [d for d in LOGS_DIR.iterdir() if d.is_dir() and (d / "meta.json").exists()],
        key=lambda d: d.stat().st_mtime,
        reverse=True,
    )
    print()
    for d in dirs:
        try:
            meta = json.loads((d / "meta.json").read_text())
        except Exception:
            meta = {}
        title = meta.get("title") or d.name[:20]
        status = meta.get("status", "?")
        ts = fmt_ts(meta.get("started_at", ""))
        active_marker = " ◀" if d.name == (LOGS_DIR / ".active-session").read_text().strip() else ""
        print(f"  {d.name[:8]}…  {status:<12}  {ts}  {title[:40]}{active_marker}")
    print()


# ── time formatting ───────────────────────────────────────────────────────────

def fmt_ts(iso):
    if not iso:
        return "        "
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.astimezone().strftime("%H:%M:%S")
    except Exception:
        return iso[:8] if len(iso) >= 8 else iso


# ── state machine ─────────────────────────────────────────────────────────────

def derive_node_states(events):
    active, completed = set(), set()
    for ev in events:
        if ev.get("event") == "step.enter":
            s = ev.get("step")
            if s:
                active.add(s)
                completed.discard(s)
        elif ev.get("event") == "step.exit":
            s = ev.get("step")
            if s:
                active.discard(s)
                completed.add(s)

    states = {}
    for n in NODES:
        if n in active:
            states[n] = "active"
        elif n in completed:
            states[n] = "completed"
        else:
            states[n] = "idle"

    dr_launched = any(
        ev.get("event") == "step.enter" and ev.get("step") == "DR"
        for ev in events
    )
    required = ["DR", "BI"] if dr_launched else ["BI"]
    if all(states.get(s) == "completed" for s in required):
        states["CONV"] = "active"
    if states.get("AF") == "completed" and all(states.get(s) == "completed" for s in required):
        states["CONV"] = "completed"

    return states, dr_launched


def glyph(state, launched=True):
    if not launched:
        return "·"
    return {"active": "◉", "completed": "✓", "idle": "○"}.get(state, "○")


def fmt_state_machine(node_states, dr_launched):
    FP   = glyph(node_states.get("FP",   "idle"))
    AF   = glyph(node_states.get("AF",   "idle"))
    DR   = glyph(node_states.get("DR",   "idle"), dr_launched)
    BI   = glyph(node_states.get("BI",   "idle"))
    CONV = glyph(node_states.get("CONV", "idle"))

    dr_label = "DR  ROSE-RESEARCH" if dr_launched else "DR  ROSE-RESEARCH  (skipped)"
    dr_top = "╭── ── ── ── ── ── ── ──╮" if not dr_launched else "╭──────────────────────╮"

    lines = [
        "  STATE MACHINE",
        "  " + "─" * 56,
        "",
        f"                              {DR} {dr_label}",
        f"                           {dr_top}",
        f"  {FP} FP ──▶  {AF} AF ──┤                          ├──▶  {CONV} CONV",
        f"  USER        ROSE       ╰──────────────────────╮  │",
        f"                              {BI} BI  ROSE-BACKLOG  ╯",
        "",
    ]

    # Status row
    statuses = []
    for n in NODES:
        st = node_states.get(n, "idle")
        if n == "DR" and not dr_launched:
            st = "skipped"
        statuses.append(f"{n}:{st}")
    lines.append("  " + "  ".join(statuses))
    lines.append("")
    return "\n".join(lines)


# ── sequence diagram ──────────────────────────────────────────────────────────

COL_W = 16  # chars per actor column
TS_W  = 10  # timestamp prefix


def derive_messages(events):
    msgs = []
    seen = set()
    for ev in events:
        event   = ev.get("event", "")
        step    = ev.get("step")
        ts      = ev.get("ts", "")
        payload = ev.get("payload") or {}

        key = (event, step)
        if key in seen and event in ("step.enter", "step.exit"):
            continue
        seen.add(key)

        if event == "message.user":
            preview = (payload.get("preview") or "message")[:48]
            msgs.append({"from": "user", "to": "rose", "label": preview, "ts": ts})

        elif event == "step.enter":
            if step == "FP":
                msgs.append({"from": "user", "to": "rose", "label": "feature prompt", "ts": ts})
            elif step == "AF":
                msgs.append({"from": "rose", "to": "rose", "label": "reading codebase", "ts": ts, "self": True})
            elif step == "DR":
                msgs.append({"from": "rose", "to": "rose-research", "label": "launch: deep research", "ts": ts})
            elif step == "BI":
                msgs.append({"from": "rose", "to": "rose-backlog", "label": "launch: backlog inspect", "ts": ts})

        elif event == "step.exit":
            if step == "DR":
                msgs.append({"from": "rose-research", "to": "rose", "label": "research complete", "ts": ts})
            elif step == "BI":
                msgs.append({"from": "rose-backlog", "to": "rose", "label": "backlog complete", "ts": ts})

        elif event == "message.agent":
            preview = (payload.get("preview") or "response")[:48]
            msgs.append({"from": "rose", "to": "user", "label": preview, "ts": ts})

    return msgs


def fmt_sequence(events):
    msgs = derive_messages(events)
    n = len(ACTORS)
    total_w = TS_W + n * COL_W

    def lifeline_row(highlight_col=None, char="│"):
        row = " " * TS_W
        for i in range(n):
            pipe = char if i == highlight_col else "│"
            row += pipe + " " * (COL_W - 1)
        return row

    lines = [
        "  SEQUENCE DIAGRAM",
        "  " + "─" * 56,
        "",
    ]

    # Header
    header = " " * TS_W + "".join(
        f"{a['label']:<{COL_W}}" for a in ACTORS
    )
    lines.append(header)
    lines.append(lifeline_row())

    for msg in msgs:
        ts_str   = fmt_ts(msg["ts"])
        from_id  = msg["from"]
        to_id    = msg["to"]
        label    = msg["label"]
        is_self  = msg.get("self") or from_id == to_id

        from_i = ACTOR_IDX.get(from_id, 0)
        to_i   = ACTOR_IDX.get(to_id,   0)

        # Build character array for this row
        row = list(" " * TS_W + "│" + " " * (COL_W - 1))
        for i in range(n):
            pos = TS_W + i * COL_W
            if pos < len(row):
                row[pos] = "│"
            else:
                row.extend(" " * (pos - len(row) + 1))
                row[pos] = "│"

        if is_self:
            pos = TS_W + from_i * COL_W
            annotation = f"[{label}]"
            for j, ch in enumerate(annotation):
                p = pos + 1 + j
                if p < len(row):
                    row[p] = ch
                else:
                    row.append(ch)
        else:
            left_i  = min(from_i, to_i)
            right_i = max(from_i, to_i)
            going_right = from_i < to_i

            left_pos  = TS_W + left_i  * COL_W
            right_pos = TS_W + right_i * COL_W

            # Shaft
            for p in range(left_pos + 1, right_pos):
                row[p] = "─"

            # End markers
            if going_right:
                row[left_pos]  = "├"
                row[right_pos] = "▶"
            else:
                row[left_pos]  = "◀"
                row[right_pos] = "┤"

            # Label after the right side
            label_pos = right_pos + 1
            for j, ch in enumerate(f" {label}"):
                p = label_pos + j
                if p < len(row):
                    row[p] = ch
                else:
                    row.append(ch)

        line = "".join(row)
        lines.append(f"{ts_str}  {line[TS_W:]}")
        lines.append(lifeline_row())

    if not msgs:
        lines.append(lifeline_row())
        lines.append(" " * (TS_W + n * COL_W // 2) + "(no events)")

    lines.append("")
    return "\n".join(lines)


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    session_id = resolve_session()
    events, meta = load_session(session_id)

    title   = meta.get("title") or session_id
    status  = meta.get("status", "unknown")
    started = fmt_ts(meta.get("started_at", ""))
    ended   = fmt_ts(meta.get("ended_at", ""))
    time_range = f"{started}" + (f" → {ended}" if ended.strip() else "")

    W = 58
    print()
    print("  " + "━" * W)
    print(f"  rose observe")
    print(f"  {title}")
    print(f"  {session_id[:36]}  ·  {status}  ·  {time_range}")
    print("  " + "━" * W)
    print()

    node_states, dr_launched = derive_node_states(events)
    print(fmt_state_machine(node_states, dr_launched))
    print(fmt_sequence(events))
    print("  " + "━" * W)
    print()


if __name__ == "__main__":
    main()
