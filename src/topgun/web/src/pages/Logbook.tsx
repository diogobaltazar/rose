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
  weeks: Week[];  // oldest → newest, 10 weeks
}

// ── Mock data ─────────────────────────────────────────────────────────────────
// Each series starts rough and improves: failures drop, successes climb.

function series(pairs: [number, number][]): Week[] {
  return pairs.map(([succeeded, failed]) => ({ succeeded, failed }));
}

const ENTRIES: Entry[] = [
  // ── Skills ──────────────────────────────────────────────────────────────────
  {
    name: "topgun",
    type: "skill",
    description: "End-to-end development flow — research, plan, implement, test, deploy, commit, release.",
    weeks: series([[1,4],[2,3],[4,3],[5,2],[6,2],[8,1],[9,1],[11,1],[12,0],[14,0]]),
  },
  {
    name: "topgun-mission-plan",
    type: "skill",
    description: "Interactive planning session producing GitHub issues, Obsidian tasks, and a mission UID.",
    weeks: series([[0,3],[1,2],[2,2],[4,2],[5,1],[7,1],[8,1],[9,0],[11,0],[12,0]]),
  },
  {
    name: "topgun-task",
    type: "skill",
    description: "Federated personal backlog — query, add, edit, and close tasks across GitHub and Obsidian.",
    weeks: series([[1,2],[2,2],[3,1],[5,1],[6,1],[7,0],[8,0],[9,0],[10,0],[11,0]]),
  },
  {
    name: "topgun-thought",
    type: "skill",
    description: "Personal notes assistant — create, search, browse, and edit notes across Obsidian vaults.",
    weeks: series([[0,1],[1,1],[2,1],[3,0],[5,0],[6,0],[7,0],[8,0],[9,0],[10,0]]),
  },
  {
    name: "simplify",
    type: "skill",
    description: "Review changed code for reuse, quality, and efficiency, then fix issues found.",
    weeks: series([[2,3],[3,2],[4,2],[5,2],[6,1],[7,1],[8,1],[9,0],[10,0],[11,0]]),
  },
  {
    name: "review",
    type: "skill",
    description: "Review a pull request — correctness, style, security, and test coverage.",
    weeks: series([[1,2],[2,2],[3,1],[4,1],[5,1],[6,0],[7,0],[8,0],[9,0],[10,0]]),
  },
  {
    name: "security-review",
    type: "skill",
    description: "Complete a security review of pending changes — OWASP, secrets, injection, auth.",
    weeks: series([[0,2],[1,2],[2,1],[3,1],[4,1],[5,0],[6,0],[7,0],[8,0],[9,0]]),
  },
  // ── Commands ─────────────────────────────────────────────────────────────────
  {
    name: "less-permission-prompts",
    type: "command",
    description: "Scan transcripts for common read-only calls, add a prioritised allowlist to settings.",
    weeks: series([[0,1],[0,1],[1,1],[1,0],[2,0],[3,0],[3,0],[4,0],[4,0],[5,0]]),
  },
  {
    name: "update-config",
    type: "command",
    description: "Configure Claude Code harness via settings.json — hooks, permissions, env vars.",
    weeks: series([[1,2],[1,2],[2,1],[3,1],[4,0],[4,0],[5,0],[5,0],[6,0],[6,0]]),
  },
  {
    name: "schedule",
    type: "command",
    description: "Create, update, list, or run scheduled remote agents on a cron schedule.",
    weeks: series([[0,1],[1,1],[1,1],[2,0],[2,0],[3,0],[3,0],[4,0],[4,0],[5,0]]),
  },
  // ── Agents ───────────────────────────────────────────────────────────────────
  {
    name: "general-purpose",
    type: "agent",
    description: "Full-capability agent — research, search, edit files, run commands. Default workhorse.",
    weeks: series([[2,5],[3,4],[5,3],[7,3],[8,2],[10,2],[11,1],[13,1],[14,0],[15,0]]),
  },
  {
    name: "Explore",
    type: "agent",
    description: "Fast read-only agent for codebase exploration — glob, grep, read, web-fetch.",
    weeks: series([[1,2],[2,2],[3,1],[5,1],[6,1],[7,0],[8,0],[9,0],[10,0],[11,0]]),
  },
  {
    name: "Plan",
    type: "agent",
    description: "Software architect agent — designs implementation plans, identifies critical files.",
    weeks: series([[1,3],[2,2],[3,2],[4,1],[5,1],[6,1],[7,0],[8,0],[9,0],[10,0]]),
  },
];

// ── Sparkline ─────────────────────────────────────────────────────────────────

function Sparkline({ weeks }: { weeks: Week[] }) {
  const W = 160, H = 44;
  const n = weeks.length;
  const maxY = Math.max(...weeks.map(w => w.succeeded + w.failed), 1);
  const x = (i: number) => (i / (n - 1)) * W;
  const y = (v: number) => H - (v / maxY) * H;
  const pts = (vals: number[]) => vals.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const sVals = weeks.map(w => w.succeeded);
  const fVals = weeks.map(w => w.failed);

  return (
    <svg width={W} height={H} className="overflow-visible">
      {/* zero line */}
      <line x1={0} y1={H} x2={W} y2={H} stroke="rgba(255,255,255,0.04)" strokeWidth="1" />
      {/* failed */}
      <polyline points={pts(fVals)} fill="none" stroke="#ff3b30" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" opacity="0.7" />
      {/* succeeded */}
      <polyline points={pts(sVals)} fill="none" stroke="#00c853" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

// ── Entry card ────────────────────────────────────────────────────────────────

function EntryCard({ entry }: { entry: Entry }) {
  const totalSucceeded = entry.weeks.reduce((s, w) => s + w.succeeded, 0);
  const totalFailed    = entry.weeks.reduce((s, w) => s + w.failed, 0);
  const lastWeek       = entry.weeks[entry.weeks.length - 1];
  const improving      = lastWeek.failed === 0 || lastWeek.succeeded > lastWeek.failed;

  const typeCls =
    entry.type === "skill"   ? "border-cyan-hud text-cyan-hud" :
    entry.type === "command" ? "border-amber-tac/60 text-amber-tac/60" :
                               "border-green-live/60 text-green-live/60";

  return (
    <div className="tac-border p-4 flex flex-col gap-3 animate-fadeIn hover:bg-card/50 transition-colors">
      {/* header */}
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="font-mono text-xs font-bold text-text-primary truncate">{entry.name}</div>
          <p className="font-mono text-xs text-text-muted/60 mt-1 leading-relaxed line-clamp-2">{entry.description}</p>
        </div>
        <span className={`font-mono text-xs border px-1.5 py-0.5 shrink-0 tracking-widest uppercase ${typeCls}`}>
          {entry.type}
        </span>
      </div>

      {/* sparkline */}
      <div className="py-1">
        <Sparkline weeks={entry.weeks} />
        <div className="flex items-center justify-between mt-1">
          <span className="font-mono text-xs text-text-muted/40">10 weeks</span>
          {improving && <span className="font-mono text-xs text-green-live/60">↑ improving</span>}
        </div>
      </div>

      {/* totals */}
      <div className="flex items-center gap-4 pt-2 border-t border-border-dim">
        <span className="font-mono text-xs text-green-live">+{totalSucceeded} succeeded</span>
        <span className="font-mono text-xs text-red-alert">−{totalFailed} failed</span>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

type Filter = "all" | "skill" | "command" | "agent";

export default function Logbook() {
  const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();
  const [filter, setFilter] = useState<Filter>("all");

  if (!isLoading && !isAuthenticated) { loginWithRedirect(); return null; }

  const visible = filter === "all" ? ENTRIES : ENTRIES.filter(e => e.type === filter);

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
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`font-mono text-xs px-4 py-1.5 tracking-widest uppercase transition-colors ${
                  filter === f ? "bg-card text-amber-tac" : "text-text-muted hover:text-text-secondary"
                }`}
              >
                {f === "all" ? "ALL" : f + "S"}
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {visible.map((e, i) => (
            <div key={e.name} style={{ animationDelay: `${i * 0.04}s` }}>
              <EntryCard entry={e} />
            </div>
          ))}
        </div>
      </main>
    </div>
  );
}
