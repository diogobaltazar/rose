import { useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import NavBar from "../components/NavBar";
import HUDGrid from "../components/HUDGrid";

// ── Agent palette ─────────────────────────────────────────────────────────────
// Amber = Opus (premium, warm), Cyan = Sonnet (fast, cool).
// Codex excluded — it has no concept of skills, commands, or custom agents.

const AGENTS = [
  { key: "opus",   name: "Claude Code Opus 4.5",   short: "Opus",   color: "#FFB800" },
  { key: "sonnet", name: "Claude Code Sonnet 4.5", short: "Sonnet", color: "#00d4ff" },
] as const;

type EntryType = "skill" | "command" | "agent";

interface AgentWeeks { opus: number[]; sonnet: number[]; }
interface Entry {
  name: string;
  type: EntryType;
  description: string;
  // succeeded missions per agent per week (10 weeks, oldest first)
  weeks: AgentWeeks;
}

// ── Data ──────────────────────────────────────────────────────────────────────
// Characteristics:
//   Opus   — highest baseline, consistent, low variance, already strong early
//   Sonnet — starts lower, faster growth, medium variance, catches up


const ENTRIES: Entry[] = [
  {
    name: "topgun", type: "skill",
    description: "End-to-end development flow — research, plan, implement, test, deploy, commit, release to alpha. Covers GitHub issue management, worktree-based branching, verification loops, and deployment monitoring.",
    weeks: {
      opus:   [3,4,5,4,7,8,7,10,11,12],
      sonnet: [1,2,3,3,5,6,8, 7,10,11],
    },
  },
  {
    name: "topgun-mission-plan", type: "skill",
    description: "Mission planner — interactive planning session that produces GitHub issues, Obsidian tasks, and a mission UID stored in Redis.",
    weeks: {
      opus:   [2,3,4,3,5,7,8, 9,11,12],
      sonnet: [1,1,3,2,4,5,6, 7, 9,10],
    },
  },
  {
    name: "topgun-task", type: "skill",
    description: "Federated personal backlog — query, add, edit, and close tasks across GitHub repos and Obsidian vaults in natural language.",
    weeks: {
      opus:   [2,3,5,4,6,7,7,8,10,11],
      sonnet: [1,2,3,4,5,6,5,7, 8,10],
    },
  },
  {
    name: "topgun-thought", type: "skill",
    description: "Personal notes assistant — create, search, browse, and edit notes across Obsidian vaults in natural language.",
    weeks: {
      opus:   [3,5,6,6,8,8,9,9,10,10],
      sonnet: [2,3,4,5,6,7,7,8, 9,10],
    },
  },
  {
    name: "simplify", type: "skill",
    description: "Review changed code for reuse, quality, and efficiency, then fix any issues found.",
    weeks: {
      opus:   [2,3,3,5,4,7,7,9, 9,11],
      sonnet: [1,2,3,3,5,5,6,7, 8, 9],
    },
  },
  {
    name: "review", type: "skill",
    description: "Review a pull request — correctness, style, security, and test coverage.",
    weeks: {
      opus:   [2,3,4,5,6,6,8,8,9,10],
      sonnet: [1,2,3,4,5,6,6,7,8, 9],
    },
  },
  {
    name: "security-review", type: "skill",
    description: "Complete a security review of the pending changes — OWASP top 10, secrets exposure, injection, auth flows.",
    weeks: {
      opus:   [1,2,3,3,5,6,7,7,9, 9],
      sonnet: [0,1,2,3,4,4,6,6,7, 8],
    },
  },
  {
    name: "less-permission-prompts", type: "command",
    description: "Scan transcripts for common read-only tool calls, then add a prioritised allowlist to project settings.json.",
    weeks: {
      opus:   [1,2,3,4,4,5,5,6,6,7],
      sonnet: [1,1,2,3,4,4,5,5,6,6],
    },
  },
  {
    name: "update-config", type: "command",
    description: "Configure the Claude Code harness via settings.json — hooks, permissions, env vars.",
    weeks: {
      opus:   [2,3,4,4,6,6,7,7,8,8],
      sonnet: [1,2,3,4,5,5,6,7,7,8],
    },
  },
  {
    name: "schedule", type: "command",
    description: "Create, update, list, or run scheduled remote agents on a cron schedule.",
    weeks: {
      opus:   [1,2,3,4,4,5,5,6,6,7],
      sonnet: [0,1,2,3,4,4,5,5,6,6],
    },
  },
  {
    name: "general-purpose", type: "agent",
    description: "Full-capability agent — research, search, edit files, run commands, spawn subagents. Default workhorse for multi-step implementation tasks.",
    weeks: {
      opus:   [3,4,5,5,7,7,8,10,11,13],
      sonnet: [2,3,4,4,5,7,7, 9,10,11],
    },
  },
  {
    name: "Explore", type: "agent",
    description: "Fast read-only agent for codebase exploration — glob, grep, read, web-fetch. Three thoroughness levels.",
    weeks: {
      opus:   [2,3,5,5,7,7,8,8,10,11],
      sonnet: [1,3,4,5,6,6,7,8, 9,10],
    },
  },
  {
    name: "Plan", type: "agent",
    description: "Software architect agent for designing implementation plans. Returns step-by-step plans, identifies critical files, considers trade-offs.",
    weeks: {
      opus:   [2,3,4,4,6,7,7,8,9,10],
      sonnet: [1,2,3,4,5,5,7,7,8, 9],
    },
  },
];

// ── Sparkline ─────────────────────────────────────────────────────────────────

function Sparkline({
  weeks, width = 160, height = 44, showLabels = false, showGrid = false,
}: {
  weeks: AgentWeeks; width?: number; height?: number;
  showLabels?: boolean; showGrid?: boolean;
}) {
  const n = 10;
  const allVals = [...weeks.opus, ...weeks.sonnet];
  const maxY = Math.max(...allVals, 1);
  const x = (i: number) => (i / (n - 1)) * width;
  const y = (v: number) => height - (v / maxY) * (height - 4) - 2;
  const pts = (vals: number[]) =>
    vals.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");

  return (
    <svg width={width} height={height + (showLabels ? 18 : 0)} className="overflow-visible">
      {showGrid && [0.25, 0.5, 0.75, 1].map(t => (
        <line key={t} x1={0} y1={y(maxY * t)} x2={width} y2={y(maxY * t)}
          stroke="rgba(255,255,255,0.04)" strokeWidth="1" />
      ))}
      {AGENTS.map(a => (
        <polyline key={a.key} points={pts(weeks[a.key])}
          fill="none" stroke={a.color} strokeWidth={showLabels ? 2 : 1.5}
          strokeLinecap="round" strokeLinejoin="round" />
      ))}
      {/* terminal dots */}
      {AGENTS.map(a => (
        <circle key={a.key} cx={x(n-1)} cy={y(weeks[a.key][n-1])} r={showLabels ? 3 : 2}
          fill={a.color} />
      ))}
      {showLabels && Array.from({length: n}, (_, i) => (
        <text key={i} x={x(i)} y={height + 14} textAnchor="middle"
          style={{ fontSize: 9, fontFamily: "IBM Plex Mono, monospace", fill: "rgba(255,255,255,0.3)" }}>
          W{i + 1}
        </text>
      ))}
    </svg>
  );
}

// ── Legend ────────────────────────────────────────────────────────────────────

function Legend({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`flex items-center ${compact ? "gap-3" : "gap-5"}`}>
      {AGENTS.map(a => (
        <span key={a.key} className="flex items-center gap-1.5">
          <span className="inline-block rounded-full" style={{ width: compact ? 20 : 24, height: 2, background: a.color, opacity: 1 }} />
          <span className="font-mono tracking-wide" style={{ fontSize: compact ? 9 : 10, color: "rgba(255,255,255,0.45)" }}>
            {compact ? a.short : a.name}
          </span>
        </span>
      ))}
    </div>
  );
}

// ── Compact card ──────────────────────────────────────────────────────────────

function EntryCardCompact({ entry, onClick, index }: {
  entry: Entry; onClick: () => void; index: number;
}) {
  const totals = AGENTS.map(a => entry.weeks[a.key].reduce((s, v) => s + v, 0));
  const leader = AGENTS[totals.indexOf(Math.max(...totals))];
  const typeCls =
    entry.type === "skill"   ? "border-cyan-hud text-cyan-hud" :
    entry.type === "command" ? "border-amber-tac/60 text-amber-tac/60" :
                               "border-green-live/60 text-green-live/60";

  return (
    <button onClick={onClick}
      className="tac-border p-4 flex flex-col gap-3 hover:bg-card/60 transition-colors text-left w-full animate-fadeIn"
      style={{ animationDelay: `${index * 0.04}s` }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="font-mono text-xs font-bold text-text-primary truncate">{entry.name}</div>
        <span className={`font-mono text-xs border px-1.5 py-0.5 shrink-0 tracking-widest uppercase ${typeCls}`}>
          {entry.type}
        </span>
      </div>

      <div>
        <Legend compact />
        <div className="mt-2">
          <Sparkline weeks={entry.weeks} />
        </div>
      </div>

      <div className="flex items-center justify-between pt-2 border-t border-border-dim">
        <span className="font-mono text-xs flex items-center gap-1.5">
          <span className="inline-block w-2 h-2 rounded-full" style={{ background: leader.color }} />
          <span className="text-text-muted/60">{leader.short} leads</span>
        </span>
        <span className="font-mono text-xs text-text-muted/40">▶</span>
      </div>
    </button>
  );
}

// ── Expanded card ─────────────────────────────────────────────────────────────

function EntryCardExpanded({ entry, onClose }: { entry: Entry; onClose: () => void }) {
  const n = 10;
  const typeCls =
    entry.type === "skill"   ? "border-cyan-hud text-cyan-hud" :
    entry.type === "command" ? "border-amber-tac/60 text-amber-tac/60" :
                               "border-green-live/60 text-green-live/60";

  const agentStats = AGENTS.map(a => {
    const vals = entry.weeks[a.key];
    const total = vals.reduce((s, v) => s + v, 0);
    const last  = vals[n - 1];
    const first = vals[0];
    const peak  = Math.max(...vals);
    const delta = last - first;
    return { ...a, total, last, first, peak, delta };
  });

  const maxY = Math.max(...AGENTS.flatMap(a => entry.weeks[a.key]), 1);

  return (
    <div className="tac-border animate-fadeIn">
      {/* Header */}
      <div className="flex items-start justify-between px-6 py-5 border-b border-border-dim">
        <div className="flex-1 min-w-0 pr-4">
          <div className="flex items-center gap-3 mb-2">
            <span className="font-mono text-lg font-bold text-text-primary">{entry.name}</span>
            <span className={`font-mono text-xs border px-1.5 py-0.5 tracking-widest uppercase ${typeCls}`}>
              {entry.type}
            </span>
          </div>
          <p className="font-mono text-xs text-text-muted leading-relaxed">{entry.description}</p>
        </div>
        <button onClick={onClose} className="font-mono text-xs text-text-muted hover:text-amber-tac shrink-0">✕</button>
      </div>

      {/* Chart */}
      <div className="px-6 pt-5 pb-4">
        <div className="flex items-center justify-between mb-4">
          <span className="font-mono text-xs text-text-muted/50 tracking-widest">MISSIONS SUCCEEDED / WEEK</span>
          <Legend />
        </div>
        <Sparkline weeks={entry.weeks} width={600} height={100} showLabels showGrid />
      </div>

      {/* Per-agent stats */}
      <div className="grid grid-cols-3 gap-3 px-6 py-4 border-t border-border-dim">
        {agentStats.map(a => (
          <div key={a.key} className="border border-border-dim p-4 space-y-3">
            <div className="flex items-center gap-2">
              <span className="inline-block w-3 h-3 rounded-full" style={{ background: a.color, opacity: 1 }} />
              <span className="font-mono text-xs font-bold" style={{ color: a.color, opacity: 1 }}>
                {a.short}
              </span>
            </div>
            <div className="font-mono text-xs text-text-muted/60 leading-none">{a.name}</div>
            <div className="grid grid-cols-2 gap-2 pt-1">
              {[
                { label: "TOTAL",  value: String(a.total) },
                { label: "PEAK",   value: String(a.peak) + " /wk" },
                { label: "LATEST", value: String(a.last) + " /wk" },
                { label: "DELTA",  value: (a.delta >= 0 ? "+" : "") + a.delta },
              ].map(s => (
                <div key={s.label}>
                  <div className={`font-mono text-sm font-bold ${
                    s.label === "DELTA" ? (a.delta >= 0 ? "text-green-live" : "text-red-alert") : "text-text-primary"
                  }`}>{s.value}</div>
                  <div className="font-mono text-xs text-text-muted/50 tracking-widest mt-0.5">{s.label}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>

      {/* Week breakdown table */}
      <div className="px-6 py-4 border-t border-border-dim">
        <div className="font-mono text-xs text-text-muted/50 tracking-widest uppercase mb-3">Week breakdown</div>
        <div className="grid gap-1.5" style={{ gridTemplateColumns: `repeat(${n}, 1fr)` }}>
          {Array.from({length: n}, (_, i) => {
            const vals = AGENTS.map(a => entry.weeks[a.key][i]);
            const total = vals.reduce((s, v) => s + v, 0);
            const barH = Math.max(4, Math.round((total / (maxY * AGENTS.length)) * 56));
            return (
              <div key={i} className="flex flex-col items-center gap-1">
                <div className="flex flex-col-reverse gap-px w-full" style={{ height: 60 }}>
                  {AGENTS.map((a, j) => {
                    const h = Math.round((vals[j] / Math.max(total, 1)) * barH);
                    return h > 0 ? (
                      <div key={a.key} className="w-full rounded-sm"
                        style={{ height: h, background: a.color, opacity: 0.85 }} />
                    ) : null;
                  })}
                </div>
                <div style={{ fontSize: 9, fontFamily: "IBM Plex Mono, monospace", color: "rgba(255,255,255,0.3)" }}>
                  W{i + 1}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type Filter = "all" | "skill" | "command" | "agent";

export default function Logbook() {
  const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();
  const [filter, setFilter] = useState<Filter>("all");
  const [selected, setSelected] = useState<string | null>(null);

  if (!isLoading && !isAuthenticated) { loginWithRedirect(); return null; }

  const all = filter === "all" ? ENTRIES : ENTRIES.filter(e => e.type === filter);
  const selectedIdx   = selected ? all.findIndex(e => e.name === selected) : -1;
  const selectedEntry = selectedIdx >= 0 ? all[selectedIdx] : null;
  const before = selectedIdx >= 0 ? all.slice(0, selectedIdx) : all;
  const after  = selectedIdx >= 0 ? all.slice(selectedIdx + 1) : [];

  const toggle = (name: string) => setSelected(v => v === name ? null : name);

  const grid = (entries: Entry[], offset = 0) => (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {entries.map((e, i) => (
        <EntryCardCompact key={e.name} entry={e} onClick={() => toggle(e.name)} index={offset + i} />
      ))}
    </div>
  );

  return (
    <div className="min-h-screen bg-base text-text-primary">
      <HUDGrid />
      <NavBar />
      <main className="relative z-10 max-w-6xl mx-auto px-6 py-10">
        <div className="flex items-end justify-between mb-8">
          <div>
            <div className="font-mono text-xs text-amber-tac tracking-[0.4em] uppercase mb-1">Command Deck</div>
            <h1 className="font-mono text-xl font-semibold">Logbook</h1>
            <p className="font-mono text-xs text-text-muted mt-1">
              Accumulated experience — skills, commands, and agents through time
            </p>
          </div>
          <div className="flex items-center gap-0 border border-border-dim">
            {(["all", "skill", "command", "agent"] as Filter[]).map(f => (
              <button key={f} onClick={() => { setFilter(f); setSelected(null); }}
                className={`font-mono text-xs px-4 py-1.5 tracking-widest uppercase transition-colors ${
                  filter === f ? "bg-card text-amber-tac" : "text-text-muted hover:text-text-secondary"
                }`}>
                {f === "all" ? "ALL" : f + "S"}
              </button>
            ))}
          </div>
        </div>

        <div className="space-y-4">
          {before.length > 0 && grid(before)}
          {selectedEntry && <EntryCardExpanded entry={selectedEntry} onClose={() => setSelected(null)} />}
          {after.length > 0 && grid(after, before.length)}
        </div>
      </main>
    </div>
  );
}
