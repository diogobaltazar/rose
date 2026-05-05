import { useEffect, useState, useMemo } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import NavBar from "../components/NavBar";
import HUDGrid from "../components/HUDGrid";
import { useEngagement, type EngagedMission } from "../context/EngagementContext";

// ── Helpers ───────────────────────────────────────────────────────────────────

function fmtElapsed(ms: number): string {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}
function fmtNum(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}
function fmtUsd(n: number): string { return `$${n.toFixed(3)}`; }
function rand(min: number, max: number) { return Math.floor(Math.random() * (max - min + 1)) + min; }
function hash(uid: string, salt = 0) {
  return uid.split("").reduce((a, c, i) => a + c.charCodeAt(0) * (i + salt + 1), 0);
}

// ── Mission graph types ───────────────────────────────────────────────────────

type NodeStatus = "pending" | "running" | "done" | "failed";

interface GraphNode {
  id: string;
  pilot: string;
  model: string;
  task: string;
  level: number;
  posInLevel: number;
  duration: number;  // ms
  willFail: boolean;
}

// ── Graph construction ────────────────────────────────────────────────────────
// Structures: each element is the node count at that level.
// First and last level always have 1 node (Maverick).

const STRUCTURES = [
  [1, 2, 1],
  [1, 3, 1],
  [1, 2, 2, 1],
  [1, 1, 2, 1],
];

const TASKS_BY_LEVEL = [
  ["Analyse requirements", "Map codebase", "Read issue context"],
  ["Implement core logic", "Write unit tests", "Refactor module", "Update types"],
  ["Integrate changes", "Fix edge cases", "Security check", "Performance pass"],
  ["Final review", "Merge & tag", "Verify deploy"],
];

const NON_MAVERICK = ["ICEMAN", "ROOSTER", "PHOENIX", "HANGMAN", "BOB"];

function buildGraph(uid: string): GraphNode[] {
  const h0 = hash(uid);
  const structure = STRUCTURES[h0 % STRUCTURES.length];
  const w1 = NON_MAVERICK[h0 % NON_MAVERICK.length];
  const w2 = NON_MAVERICK[(h0 + 2) % NON_MAVERICK.length] === w1
    ? NON_MAVERICK[(h0 + 3) % NON_MAVERICK.length]
    : NON_MAVERICK[(h0 + 2) % NON_MAVERICK.length];

  const models: Record<string, string> = { MAVERICK: "Opus 4.5", [w1]: "Sonnet 4.5", [w2]: "Sonnet 4.5" };
  const willFail = h0 % 3 === 0; // ~1 in 3 missions fail

  const nodes: GraphNode[] = [];
  let idx = 0;

  structure.forEach((count, level) => {
    const pilots = count === 1 ? ["MAVERICK"] : count === 2 ? ["MAVERICK", w1] : ["MAVERICK", w1, w2];
    for (let pos = 0; pos < count; pos++) {
      const pool = TASKS_BY_LEVEL[Math.min(level, TASKS_BY_LEVEL.length - 1)];
      nodes.push({
        id: `n${idx}`,
        pilot: pilots[pos],
        model: models[pilots[pos]] ?? "Sonnet 4.5",
        task: pool[(idx + h0) % pool.length],
        level,
        posInLevel: pos,
        // Non-linear durations: vary by node index and uid
        duration: 3200 + (hash(uid, idx + 1) % 37) * 100,
        willFail: false,
      });
      idx++;
    }
  });

  // Mark a middle-level node to fail (never first or last level)
  if (willFail) {
    const candidates = nodes.filter(n => n.level > 0 && n.level < structure.length - 1);
    if (candidates.length > 0) {
      candidates[(h0 * 7) % candidates.length].willFail = true;
    }
  }

  return nodes;
}

// ── Animation hook ────────────────────────────────────────────────────────────

function useMissionAnimation(nodes: GraphNode[]): {
  statuses: Record<string, NodeStatus>;
  outcome: "running" | "succeeded" | "failed";
} {
  const [statuses, setStatuses] = useState<Record<string, NodeStatus>>(() =>
    Object.fromEntries(nodes.map(n => [n.id, "pending" as NodeStatus]))
  );
  const [outcome, setOutcome] = useState<"running" | "succeeded" | "failed">("running");

  useEffect(() => {
    let cancelled = false;
    const levels = [...new Set(nodes.map(n => n.level))].sort((a, b) => a - b);

    async function run() {
      await new Promise(r => setTimeout(r, 600)); // initial pause

      for (const level of levels) {
        if (cancelled) return;
        const lvNodes = nodes.filter(n => n.level === level);

        // Start all nodes at this level simultaneously
        setStatuses(prev => {
          const next = { ...prev };
          lvNodes.forEach(n => { next[n.id] = "running"; });
          return next;
        });

        // Wait for ALL to finish (concurrently)
        await Promise.all(lvNodes.map(n => new Promise<void>(r => setTimeout(r, n.duration))));
        if (cancelled) return;

        // Check failures
        const failing = lvNodes.find(n => n.willFail);
        if (failing) {
          setStatuses(prev => {
            const next = { ...prev };
            lvNodes.forEach(n => { next[n.id] = n.willFail ? "failed" : "done"; });
            return next;
          });
          setOutcome("failed");
          return;
        }

        setStatuses(prev => {
          const next = { ...prev };
          lvNodes.forEach(n => { next[n.id] = "done"; });
          return next;
        });
      }
      if (!cancelled) setOutcome("succeeded");
    }

    const t = setTimeout(() => run(), 0);
    return () => { cancelled = true; clearTimeout(t); };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  return { statuses, outcome };
}

// ── Node box ──────────────────────────────────────────────────────────────────

const NODE_W = 148;
const NODE_H = 76;
const LEVEL_GAP = 210;
const NODE_VGAP = 90;

function NodeBox({ node, status }: { node: GraphNode; status: NodeStatus }) {
  const border = status === "running" ? "border-amber-tac" : status === "done" ? "border-green-live" : status === "failed" ? "border-red-alert" : "border-border-dim";
  const pilot  = status === "running" ? "text-amber-tac" : status === "done" ? "text-green-live" : status === "failed" ? "text-red-alert" : "text-text-muted/30";
  const task   = status === "pending" ? "text-text-muted/20" : "text-text-muted/60";
  const icon   = status === "done" ? "✓" : status === "failed" ? "✗" : status === "running" ? "" : "";

  return (
    <div className={`border ${border} bg-[#0e0e0e] h-full p-3 flex flex-col justify-between select-none`}>
      {/* Running pulse border overlay */}
      {status === "running" && (
        <div className="absolute inset-0 border border-amber-tac animate-pulse_amber pointer-events-none" />
      )}
      <div>
        <div className={`font-mono text-xs font-bold ${pilot} flex items-center justify-between`}>
          <span className="flex items-center gap-1.5">
            <span>✈</span>
            <span>{node.pilot}</span>
          </span>
          {icon && <span>{icon}</span>}
          {status === "running" && (
            <span className="w-1.5 h-1.5 rounded-full bg-amber-tac animate-pulse_amber shrink-0" />
          )}
        </div>
        <div className={`font-mono text-xs mt-1.5 leading-snug ${task}`}>{node.task}</div>
      </div>
      <div className="font-mono text-xs text-text-muted/30">{node.model}</div>
    </div>
  );
}

// ── Mission graph viz ─────────────────────────────────────────────────────────

function MissionGraphViz({ uid }: { uid: string }) {
  const nodes = useMemo(() => buildGraph(uid), [uid]);
  const { statuses, outcome } = useMissionAnimation(nodes);

  const maxLevel = Math.max(...nodes.map(n => n.level));
  const maxPerLevel = Math.max(...Array.from({ length: maxLevel + 1 }, (_, l) =>
    nodes.filter(n => n.level === l).length
  ));

  const totalW = NODE_W * (maxLevel + 1) + (LEVEL_GAP - NODE_W) * maxLevel + 32;
  const totalH = NODE_H + (maxPerLevel - 1) * NODE_VGAP + 40;

  const getPos = (node: GraphNode) => {
    const lvNodes = nodes.filter(n => n.level === node.level);
    const lvH = (lvNodes.length - 1) * NODE_VGAP + NODE_H;
    return {
      x: 16 + node.level * LEVEL_GAP,
      y: (totalH - lvH) / 2 + node.posInLevel * NODE_VGAP,
    };
  };

  // Edges: every node at level L → every node at level L+1
  const edges: { from: GraphNode; to: GraphNode }[] = [];
  for (let l = 0; l < maxLevel; l++) {
    nodes.filter(n => n.level === l).forEach(from =>
      nodes.filter(n => n.level === l + 1).forEach(to => edges.push({ from, to }))
    );
  }

  return (
    <div className="overflow-x-auto">
      <div className="relative" style={{ width: totalW, height: totalH }}>
        {/* Edges */}
        <svg className="absolute inset-0 pointer-events-none" width={totalW} height={totalH}>
          {edges.map(({ from, to }, i) => {
            const fp = getPos(from), tp = getPos(to);
            const x1 = fp.x + NODE_W, y1 = fp.y + NODE_H / 2;
            const x2 = tp.x,          y2 = tp.y + NODE_H / 2;
            const gap = LEVEL_GAP - NODE_W;
            const fromS = statuses[from.id], toS = statuses[to.id];
            const stroke =
              fromS === "failed" || toS === "failed" ? "#ff3b30" :
              fromS === "done" && toS === "done"     ? "#00c853" :
              fromS === "done"                        ? "#FFB800" :
              "rgba(255,255,255,0.08)";
            return (
              <path key={i}
                d={`M ${x1} ${y1} C ${x1 + gap * 0.45} ${y1}, ${x2 - gap * 0.45} ${y2}, ${x2} ${y2}`}
                fill="none" stroke={stroke} strokeWidth="1.5"
                opacity={fromS === "pending" ? 0.25 : 0.9}
              />
            );
          })}
        </svg>

        {/* Nodes */}
        {nodes.map(node => {
          const pos = getPos(node);
          return (
            <div key={node.id} className="absolute" style={{ left: pos.x, top: pos.y, width: NODE_W, height: NODE_H }}>
              <NodeBox node={node} status={statuses[node.id]} />
            </div>
          );
        })}
      </div>

      {/* Outcome */}
      {outcome !== "running" && (
        <div className="mt-4 animate-fadeIn">
          {outcome === "succeeded"
            ? <span className="font-mono text-xs text-green-live tracking-widest">✓ MISSION SUCCEEDED</span>
            : <span className="font-mono text-xs text-red-alert tracking-widest">✗ MISSION FAILED — agent aborted</span>
          }
        </div>
      )}
    </div>
  );
}

// ── Globals ───────────────────────────────────────────────────────────────────

function GlobeIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.5" strokeLinecap="round">
      <circle cx="12" cy="12" r="10" /><ellipse cx="12" cy="12" rx="4" ry="10" /><line x1="2" y1="12" x2="22" y2="12" />
    </svg>
  );
}

function FlashValue({ value, className = "" }: { value: string; className?: string }) {
  return <span key={value} className={`animate-flash tabular-nums ${className}`}>{value}</span>;
}

// ── Crew config ───────────────────────────────────────────────────────────────

const NON_MAVERICK_LIST = ["ICEMAN", "ROOSTER", "PHOENIX", "HANGMAN", "BOB"];
const CREW_CONFIG = [
  { role: "TEAM LEAD",  model: "Opus 4.5",   tokRate: 0.000015, toolsPerTick: [2, 4] as [number, number], tokPerTick: [800, 1800] as [number, number], brief: "Driving architecture decisions, implementing core changes, and authoring the final PR." },
  { role: "WINGMAN",   model: "Sonnet 4.5",  tokRate: 0.000003, toolsPerTick: [1, 3] as [number, number], tokPerTick: [400, 1200] as [number, number], brief: "Writing tests, handling edge cases, refining documentation, and providing review support." },
];

function pickWingman(uid: string): string {
  const h = hash(uid);
  return NON_MAVERICK_LIST[h % NON_MAVERICK_LIST.length];
}

// ── Pilot card ────────────────────────────────────────────────────────────────

interface PilotTelemetry { tools: number; tokens: number; usd: number; }

function PilotCard({ cfg, name, telemetry }: { cfg: typeof CREW_CONFIG[0]; name: string; telemetry: PilotTelemetry }) {
  return (
    <div className="border border-border-dim p-4 space-y-3 flex-1">
      <div className="flex items-center gap-2">
        <span className="text-amber-tac">✈</span>
        <span className="font-mono text-xs text-amber-tac tracking-widest">{cfg.role}</span>
      </div>
      <div>
        <div className="font-mono text-sm font-bold text-text-primary">{name}</div>
        <div className="font-mono text-xs text-text-muted mt-0.5">Anthropic Claude Code · {cfg.model}</div>
      </div>
      <p className="font-mono text-xs text-text-muted/60 leading-relaxed">{cfg.brief}</p>
      <div className="grid grid-cols-3 gap-2 pt-1 border-t border-border-dim">
        {[
          { label: "TOOLS",  value: String(telemetry.tools) },
          { label: "TOKENS", value: fmtNum(telemetry.tokens) },
          { label: "COST",   value: fmtUsd(telemetry.usd) },
        ].map(s => (
          <div key={s.label} className="text-center pt-2">
            <div className="font-mono text-sm font-bold text-text-primary"><FlashValue value={s.value} /></div>
            <div className="font-mono text-xs text-text-muted/60 tracking-widest mt-0.5">{s.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Mission card ──────────────────────────────────────────────────────────────

function MissionCard({ mission }: { mission: EngagedMission }) {
  const { abort } = useEngagement();
  const [elapsed, setElapsed] = useState(Date.now() - mission.startedAt.getTime());
  const [wingman] = useState(() => pickWingman(mission.uid));

  type TelArr = [PilotTelemetry, PilotTelemetry];
  const [telemetry, setTelemetry] = useState<TelArr>([
    { tools: 0, tokens: 0, usd: 0 },
    { tools: 0, tokens: 0, usd: 0 },
  ]);

  useEffect(() => {
    const clock = setInterval(() => setElapsed(Date.now() - mission.startedAt.getTime()), 1000);
    return () => clearInterval(clock);
  }, [mission.startedAt]);

  useEffect(() => {
    const tick = setInterval(() => {
      setTelemetry(prev => prev.map((p, i) => {
        const cfg = CREW_CONFIG[i];
        const tools  = p.tools + rand(...cfg.toolsPerTick);
        const tokens = p.tokens + rand(...cfg.tokPerTick);
        return { tools, tokens, usd: tokens * cfg.tokRate };
      }) as TelArr);
    }, 2500);
    return () => clearInterval(tick);
  }, []);

  const totalTools  = telemetry[0].tools + telemetry[1].tools;
  const totalTokens = telemetry[0].tokens + telemetry[1].tokens;
  const totalUsd    = telemetry[0].usd + telemetry[1].usd;
  const envId = `workspace-tgun-${mission.uid.slice(0, 6)}.gitpod.io`;

  return (
    <div className="tac-border animate-fadeIn">
      {/* Header */}
      <div className="flex items-start justify-between px-6 py-5 border-b border-border-dim">
        <div>
          <div className="font-mono text-xs text-amber-tac tracking-[0.3em] uppercase mb-1">Active Mission</div>
          <div className="font-mono text-sm font-bold text-text-primary leading-snug">{mission.title}</div>
          <div className="font-mono text-xs text-text-muted mt-1">{mission.uid}</div>
          <div className="flex items-center gap-2 mt-3"><GlobeIcon /><span className="font-mono text-xs text-text-muted">{envId}</span></div>
          <div className="font-mono text-xs text-text-muted/40 mt-1 pl-[18px]">ghcr.io/diogobaltazar/topgun/agent:latest</div>
        </div>
        <div className="text-right shrink-0 ml-6">
          <div className="font-mono text-3xl font-bold text-amber-tac tabular-nums">{fmtElapsed(elapsed)}</div>
          <div className="font-mono text-xs text-text-muted mt-1 tracking-widest">ELAPSED</div>
        </div>
      </div>

      {/* Execution graph */}
      <div className="px-6 py-5 border-b border-border-dim">
        <div className="font-mono text-xs text-text-muted/50 tracking-widest uppercase mb-4">Execution Graph</div>
        <MissionGraphViz uid={mission.uid} />
      </div>

      {/* Mission totals */}
      <div className="grid grid-cols-3 gap-3 px-6 py-4 border-b border-border-dim">
        {[
          { label: "TOTAL TOOLS",  value: String(totalTools) },
          { label: "TOTAL TOKENS", value: fmtNum(totalTokens) },
          { label: "TOTAL COST",   value: fmtUsd(totalUsd) },
        ].map(s => (
          <div key={s.label} className="border border-border-dim p-3 text-center">
            <div className="font-mono text-base font-bold text-amber-tac"><FlashValue value={s.value} /></div>
            <div className="font-mono text-xs text-text-muted tracking-widest mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Crew */}
      <div className="px-6 py-4">
        <div className="font-mono text-xs text-text-muted tracking-widest uppercase mb-3">Crew</div>
        <div className="flex gap-3">
          <PilotCard cfg={CREW_CONFIG[0]} name="MAVERICK" telemetry={telemetry[0]} />
          <PilotCard cfg={CREW_CONFIG[1]} name={wingman}  telemetry={telemetry[1]} />
        </div>
      </div>

      {/* Actions */}
      <div className="px-6 pb-5">
        <button onClick={() => abort(mission.uid)}
          className="font-mono text-xs px-4 py-1.5 border border-red-alert text-red-alert hover:bg-red-alert/10 tracking-widest">
          ABORT MISSION
        </button>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function Sortie() {
  const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();
  const { missions } = useEngagement();

  if (!isLoading && !isAuthenticated) { loginWithRedirect(); return null; }

  return (
    <div className="min-h-screen bg-base text-text-primary">
      <HUDGrid />
      <NavBar />
      <main className="relative z-10 max-w-6xl mx-auto px-6 py-10">
        <div className="mb-8">
          <div className="font-mono text-xs text-amber-tac tracking-[0.4em] uppercase mb-1">Command Deck</div>
          <h1 className="font-mono text-xl font-semibold">Sortie</h1>
          <p className="font-mono text-xs text-text-muted mt-1">Active mission engagements</p>
        </div>
        {missions.length === 0 ? (
          <div className="tac-border p-16 text-center bracket-corners">
            <p className="font-mono text-xs text-text-muted tracking-widest">NO ACTIVE MISSIONS</p>
            <p className="font-mono text-xs text-text-muted/40 mt-2">Engage a mission from Intel to begin</p>
          </div>
        ) : (
          <div className="space-y-6">
            {missions.map(m => <MissionCard key={m.uid} mission={m} />)}
          </div>
        )}
      </main>
    </div>
  );
}
