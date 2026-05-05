import { useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import NavBar from "../components/NavBar";
import HUDGrid from "../components/HUDGrid";

// ── Types ─────────────────────────────────────────────────────────────────────

type EntryType = "skill" | "command" | "agent";
interface Week { succeeded: number; failed: number; }
interface Entry {
  name: string;
  type: EntryType;
  description: string;
  weeks: Week[];
}

// ── Data — realistic, non-linear improvement curves ───────────────────────────
// Regressions, plateaus, and spikes make the data feel earned.

const ENTRIES: Entry[] = [
  // ── Skills ──────────────────────────────────────────────────────────────────
  {
    name: "topgun",
    type: "skill",
    description: "End-to-end development flow — research, plan, implement, test, deploy, commit, release to alpha. Covers GitHub issue management, worktree-based branching, verification loops, and deployment monitoring.",
    weeks: [
      {succeeded:1,failed:5},{succeeded:2,failed:4},{succeeded:4,failed:4},{succeeded:3,failed:3},
      {succeeded:6,failed:3},{succeeded:8,failed:1},{succeeded:7,failed:2},{succeeded:11,failed:1},
      {succeeded:12,failed:0},{succeeded:14,failed:1},
    ],
  },
  {
    name: "topgun-mission-plan",
    type: "skill",
    description: "Mission planner — interactive planning session that produces GitHub issues, Obsidian tasks, and a mission UID stored in Redis. Run this before /topgun to define what is to be built.",
    weeks: [
      {succeeded:0,failed:3},{succeeded:2,failed:3},{succeeded:3,failed:2},{succeeded:2,failed:3},
      {succeeded:5,failed:1},{succeeded:6,failed:1},{succeeded:8,failed:2},{succeeded:9,failed:0},
      {succeeded:11,failed:1},{succeeded:12,failed:0},
    ],
  },
  {
    name: "topgun-task",
    type: "skill",
    description: "Federated personal backlog — query, add, edit, and close tasks across GitHub repos and Obsidian vaults in natural language.",
    weeks: [
      {succeeded:1,failed:2},{succeeded:2,failed:2},{succeeded:4,failed:1},{succeeded:3,failed:2},
      {succeeded:5,failed:1},{succeeded:7,failed:0},{succeeded:6,failed:1},{succeeded:8,failed:0},
      {succeeded:10,failed:0},{succeeded:11,failed:0},
    ],
  },
  {
    name: "topgun-thought",
    type: "skill",
    description: "Personal notes assistant — create, search, browse, and edit notes across Obsidian vaults in natural language.",
    weeks: [
      {succeeded:0,failed:2},{succeeded:1,failed:1},{succeeded:2,failed:1},{succeeded:4,failed:0},
      {succeeded:3,failed:1},{succeeded:5,failed:0},{succeeded:6,failed:0},{succeeded:7,failed:0},
      {succeeded:9,failed:0},{succeeded:10,failed:0},
    ],
  },
  {
    name: "simplify",
    type: "skill",
    description: "Review changed code for reuse, quality, and efficiency, then fix any issues found. Runs after implementation to tighten up the result.",
    weeks: [
      {succeeded:2,failed:4},{succeeded:3,failed:3},{succeeded:3,failed:3},{succeeded:5,failed:2},
      {succeeded:4,failed:2},{succeeded:7,failed:1},{succeeded:8,failed:1},{succeeded:9,failed:0},
      {succeeded:11,failed:1},{succeeded:11,failed:0},
    ],
  },
  {
    name: "review",
    type: "skill",
    description: "Review a pull request — correctness, style, security, and test coverage. Produces a structured report with pass/fail criteria.",
    weeks: [
      {succeeded:1,failed:2},{succeeded:2,failed:2},{succeeded:4,failed:1},{succeeded:3,failed:1},
      {succeeded:5,failed:1},{succeeded:6,failed:0},{succeeded:8,failed:1},{succeeded:8,failed:0},
      {succeeded:9,failed:0},{succeeded:10,failed:0},
    ],
  },
  {
    name: "security-review",
    type: "skill",
    description: "Complete a security review of the pending changes on the current branch — OWASP top 10, secrets exposure, injection, auth flows.",
    weeks: [
      {succeeded:0,failed:3},{succeeded:1,failed:2},{succeeded:2,failed:2},{succeeded:3,failed:1},
      {succeeded:3,failed:2},{succeeded:5,failed:1},{succeeded:6,failed:0},{succeeded:7,failed:0},
      {succeeded:8,failed:1},{succeeded:9,failed:0},
    ],
  },
  // ── Commands ─────────────────────────────────────────────────────────────────
  {
    name: "less-permission-prompts",
    type: "command",
    description: "Scan transcripts for common read-only Bash and MCP tool calls, then add a prioritised allowlist to project settings.json to reduce permission prompts.",
    weeks: [
      {succeeded:0,failed:2},{succeeded:1,failed:1},{succeeded:1,failed:1},{succeeded:2,failed:1},
      {succeeded:2,failed:0},{succeeded:3,failed:0},{succeeded:4,failed:1},{succeeded:4,failed:0},
      {succeeded:5,failed:0},{succeeded:5,failed:0},
    ],
  },
  {
    name: "update-config",
    type: "command",
    description: "Configure the Claude Code harness via settings.json — hooks, permissions, env vars. Handles automated behaviours and keybindings.",
    weeks: [
      {succeeded:1,failed:3},{succeeded:2,failed:2},{succeeded:2,failed:2},{succeeded:4,failed:1},
      {succeeded:3,failed:2},{succeeded:5,failed:1},{succeeded:6,failed:0},{succeeded:6,failed:1},
      {succeeded:7,failed:0},{succeeded:8,failed:0},
    ],
  },
  {
    name: "schedule",
    type: "command",
    description: "Create, update, list, or run scheduled remote agents (triggers) that execute on a cron schedule.",
    weeks: [
      {succeeded:0,failed:1},{succeeded:1,failed:1},{succeeded:1,failed:0},{succeeded:2,failed:1},
      {succeeded:3,failed:0},{succeeded:3,failed:0},{succeeded:4,failed:0},{succeeded:4,failed:0},
      {succeeded:5,failed:0},{succeeded:5,failed:0},
    ],
  },
  // ── Agents ───────────────────────────────────────────────────────────────────
  {
    name: "general-purpose",
    type: "agent",
    description: "Full-capability agent — research, search, edit files, run commands, spawn subagents. Default workhorse for multi-step implementation tasks.",
    weeks: [
      {succeeded:2,failed:6},{succeeded:4,failed:5},{succeeded:5,failed:5},{succeeded:7,failed:4},
      {succeeded:6,failed:4},{succeeded:9,failed:3},{succeeded:11,failed:2},{succeeded:10,failed:2},
      {succeeded:13,failed:1},{succeeded:15,failed:1},
    ],
  },
  {
    name: "Explore",
    type: "agent",
    description: "Fast read-only agent for codebase exploration — glob, grep, read, web-fetch. Three thoroughness levels: quick, medium, very thorough.",
    weeks: [
      {succeeded:1,failed:2},{succeeded:2,failed:2},{succeeded:3,failed:1},{succeeded:5,failed:1},
      {succeeded:4,failed:1},{succeeded:6,failed:1},{succeeded:8,failed:0},{succeeded:7,failed:0},
      {succeeded:9,failed:0},{succeeded:11,failed:0},
    ],
  },
  {
    name: "Plan",
    type: "agent",
    description: "Software architect agent for designing implementation plans. Returns step-by-step plans, identifies critical files, and considers architectural trade-offs.",
    weeks: [
      {succeeded:1,failed:3},{succeeded:2,failed:3},{succeeded:3,failed:2},{succeeded:4,failed:2},
      {succeeded:3,failed:2},{succeeded:6,failed:1},{succeeded:7,failed:1},{succeeded:8,failed:0},
      {succeeded:9,failed:1},{succeeded:10,failed:0},
    ],
  },
];

// ── Sparkline ─────────────────────────────────────────────────────────────────

function Sparkline({ weeks, width = 160, height = 44, showLabels = false }: {
  weeks: Week[];
  width?: number;
  height?: number;
  showLabels?: boolean;
}) {
  const n = weeks.length;
  const maxY = Math.max(...weeks.map(w => w.succeeded + w.failed), 1);
  const x = (i: number) => (i / (n - 1)) * width;
  const y = (v: number) => height - (v / maxY) * height;
  const pts = (vals: number[]) =>
    vals.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const sVals = weeks.map(w => w.succeeded);
  const fVals = weeks.map(w => w.failed);

  return (
    <svg width={width} height={height + (showLabels ? 16 : 0)} className="overflow-visible">
      <line x1={0} y1={height} x2={width} y2={height} stroke="rgba(255,255,255,0.04)" strokeWidth="1" />
      {showLabels && weeks.map((_, i) => (
        <text key={i} x={x(i)} y={height + 14} textAnchor="middle"
          className="fill-text-muted" style={{ fontSize: 9, fontFamily: "IBM Plex Mono", fill: "rgba(255,255,255,0.3)" }}>
          W{i + 1}
        </text>
      ))}
      <polyline points={pts(fVals)} fill="none" stroke="#ff3b30" strokeWidth="1.5"
        strokeLinecap="round" strokeLinejoin="round" opacity="0.7" />
      <polyline points={pts(sVals)} fill="none" stroke="#00c853" strokeWidth="1.5"
        strokeLinecap="round" strokeLinejoin="round" />
      {/* dots on last point */}
      <circle cx={x(n-1)} cy={y(sVals[n-1])} r="2.5" fill="#00c853" />
      <circle cx={x(n-1)} cy={y(fVals[n-1])} r="2.5" fill="#ff3b30" opacity="0.7" />
    </svg>
  );
}

// ── Compact card ──────────────────────────────────────────────────────────────

function EntryCardCompact({ entry, onClick, index }: { entry: Entry; onClick: () => void; index: number }) {
  const totalSucceeded = entry.weeks.reduce((s, w) => s + w.succeeded, 0);
  const totalFailed    = entry.weeks.reduce((s, w) => s + w.failed, 0);
  const typeCls =
    entry.type === "skill"   ? "border-cyan-hud text-cyan-hud" :
    entry.type === "command" ? "border-amber-tac/60 text-amber-tac/60" :
                               "border-green-live/60 text-green-live/60";
  return (
    <button
      onClick={onClick}
      className="tac-border p-4 flex flex-col gap-3 hover:bg-card/60 transition-colors text-left w-full animate-fadeIn"
      style={{ animationDelay: `${index * 0.04}s` }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="font-mono text-xs font-bold text-text-primary truncate">{entry.name}</div>
        <span className={`font-mono text-xs border px-1.5 py-0.5 shrink-0 tracking-widest uppercase ${typeCls}`}>
          {entry.type}
        </span>
      </div>
      <Sparkline weeks={entry.weeks} />
      <div className="flex items-center gap-4 pt-2 border-t border-border-dim">
        <span className="font-mono text-xs text-green-live">+{totalSucceeded}</span>
        <span className="font-mono text-xs text-red-alert">−{totalFailed}</span>
        <span className="font-mono text-xs text-text-muted/40 ml-auto">▶</span>
      </div>
    </button>
  );
}

// ── Expanded card ─────────────────────────────────────────────────────────────

function EntryCardExpanded({ entry, onClose }: { entry: Entry; onClose: () => void }) {
  const totalSucceeded = entry.weeks.reduce((s, w) => s + w.succeeded, 0);
  const totalFailed    = entry.weeks.reduce((s, w) => s + w.failed, 0);
  const total = totalSucceeded + totalFailed;
  const rate  = total === 0 ? 0 : Math.round((totalSucceeded / total) * 100);
  const lastWeek = entry.weeks[entry.weeks.length - 1];
  const firstWeek = entry.weeks[0];
  const peakSucceed = Math.max(...entry.weeks.map(w => w.succeeded));
  const peakFail    = Math.max(...entry.weeks.map(w => w.failed));

  const typeCls =
    entry.type === "skill"   ? "border-cyan-hud text-cyan-hud" :
    entry.type === "command" ? "border-amber-tac/60 text-amber-tac/60" :
                               "border-green-live/60 text-green-live/60";

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
      <div className="px-6 pt-6 pb-4">
        <div className="flex items-center gap-4 mb-3">
          <span className="font-mono text-xs text-green-live flex items-center gap-1.5">
            <span className="inline-block w-6 h-px bg-green-live" /> succeeded
          </span>
          <span className="font-mono text-xs text-red-alert flex items-center gap-1.5">
            <span className="inline-block w-6 h-px bg-red-alert opacity-70" /> failed
          </span>
        </div>
        <Sparkline weeks={entry.weeks} width={600} height={80} showLabels />
      </div>

      {/* Stats row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 px-6 py-4 border-t border-b border-border-dim">
        {[
          { label: "TOTAL RUNS",    value: String(total) },
          { label: "SUCCEEDED",     value: `+${totalSucceeded}` },
          { label: "FAILED",        value: `−${totalFailed}` },
          { label: "SUCCESS RATE",  value: `${rate}%` },
        ].map(s => (
          <div key={s.label} className="border border-border-dim p-3 text-center">
            <div className={`font-mono text-base font-bold ${
              s.label === "SUCCEEDED" ? "text-green-live" :
              s.label === "FAILED"    ? "text-red-alert"  :
              s.label === "SUCCESS RATE" ? (rate >= 80 ? "text-green-live" : rate >= 50 ? "text-amber-tac" : "text-red-alert") :
              "text-amber-tac"
            }`}>{s.value}</div>
            <div className="font-mono text-xs text-text-muted tracking-widest mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Week table */}
      <div className="px-6 py-4">
        <div className="font-mono text-xs text-text-muted tracking-widest uppercase mb-3">Week by week</div>
        <div className="grid grid-cols-5 sm:grid-cols-10 gap-1.5">
          {entry.weeks.map((w, i) => {
            const wTotal = w.succeeded + w.failed;
            const wRate  = wTotal === 0 ? 100 : Math.round((w.succeeded / wTotal) * 100);
            const barH   = Math.max(4, Math.round((wTotal / (peakSucceed + peakFail)) * 48));
            return (
              <div key={i} className="flex flex-col items-center gap-1">
                <div className="flex flex-col-reverse gap-px w-full" style={{ height: 52 }}>
                  <div className="w-full bg-green-live/70 rounded-sm" style={{ height: Math.round(barH * (w.succeeded / Math.max(wTotal, 1))) }} />
                  <div className="w-full bg-red-alert/60 rounded-sm" style={{ height: Math.round(barH * (w.failed / Math.max(wTotal, 1))) }} />
                </div>
                <div className="font-mono text-center" style={{ fontSize: 9, color: wRate === 100 ? "#00c853" : wRate === 0 ? "#ff3b30" : "rgba(255,255,255,0.3)" }}>
                  W{i + 1}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Trend note */}
      <div className="px-6 pb-5 flex items-center gap-6">
        <div>
          <div className="font-mono text-xs text-text-muted">Started</div>
          <div className="font-mono text-xs mt-0.5">
            <span className="text-green-live">+{firstWeek.succeeded}</span>
            {" / "}
            <span className="text-red-alert">−{firstWeek.failed}</span>
          </div>
        </div>
        <div className="flex-1 h-px bg-border-dim" />
        <div>
          <div className="font-mono text-xs text-text-muted">Latest</div>
          <div className="font-mono text-xs mt-0.5">
            <span className="text-green-live">+{lastWeek.succeeded}</span>
            {" / "}
            <span className="text-red-alert">−{lastWeek.failed}</span>
          </div>
        </div>
        <div className="flex-1 h-px bg-border-dim" />
        <div>
          <div className="font-mono text-xs text-text-muted">Peak run</div>
          <div className="font-mono text-xs text-amber-tac mt-0.5">{peakSucceed} missions</div>
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
  const selectedIdx = selected ? all.findIndex(e => e.name === selected) : -1;
  const selectedEntry = selectedIdx >= 0 ? all[selectedIdx] : null;
  const before = selectedIdx >= 0 ? all.slice(0, selectedIdx) : all;
  const after  = selectedIdx >= 0 ? all.slice(selectedIdx + 1) : [];

  const toggle = (name: string) => setSelected(v => v === name ? null : name);

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
          {before.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {before.map((e, i) => (
                <EntryCardCompact key={e.name} entry={e} onClick={() => toggle(e.name)} index={i} />
              ))}
            </div>
          )}
          {selectedEntry && (
            <EntryCardExpanded entry={selectedEntry} onClose={() => setSelected(null)} />
          )}
          {after.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {after.map((e, i) => (
                <EntryCardCompact key={e.name} entry={e} onClick={() => toggle(e.name)} index={i} />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
