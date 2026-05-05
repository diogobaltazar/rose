import { useEffect, useState } from "react";
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

// ── Config ────────────────────────────────────────────────────────────────────

const NON_MAVERICK = ["ICEMAN", "ROOSTER", "PHOENIX", "HANGMAN", "BOB"];

function pickWingman(uid: string): string {
  const hash = uid.split("").reduce((a, c) => a + c.charCodeAt(0), 0);
  return NON_MAVERICK[hash % NON_MAVERICK.length];
}

const CREW_CONFIG = [
  {
    role: "TEAM LEAD",
    model: "Opus 4.5",
    tokRate: 0.000015,
    toolsPerTick: [2, 4] as [number, number],
    tokPerTick:   [800, 1800] as [number, number],
    brief: "Driving architecture decisions, implementing core changes, and authoring the final PR.",
  },
  {
    role: "WINGMAN",
    model: "Sonnet 4.5",
    tokRate: 0.000003,
    toolsPerTick: [1, 3] as [number, number],
    tokPerTick:   [400, 1200] as [number, number],
    brief: "Writing tests, handling edge cases, refining documentation, and providing review support.",
  },
];

function rand(min: number, max: number) { return Math.floor(Math.random() * (max - min + 1)) + min; }

// ── Globe SVG ─────────────────────────────────────────────────────────────────

function GlobeIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.5" strokeLinecap="round">
      <circle cx="12" cy="12" r="10" />
      <ellipse cx="12" cy="12" rx="4" ry="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
    </svg>
  );
}

// ── Flash value ───────────────────────────────────────────────────────────────
// Re-keying on value change triggers CSS animation fresh each tick.

function FlashValue({ value, className = "" }: { value: string; className?: string }) {
  return (
    <span key={value} className={`animate-flash tabular-nums ${className}`}>
      {value}
    </span>
  );
}

// ── Pilot card ────────────────────────────────────────────────────────────────

interface PilotTelemetry { tools: number; tokens: number; usd: number; }

function PilotCard({ cfg, name, telemetry }: {
  cfg: typeof CREW_CONFIG[0];
  name: string;
  telemetry: PilotTelemetry;
}) {
  return (
    <div className="border border-border-dim p-4 space-y-3 flex-1">
      <div className="flex items-center gap-2">
        <span className="text-amber-tac">✈</span>
        <span className="font-mono text-xs text-amber-tac tracking-widest">{cfg.role}</span>
      </div>
      <div>
        <div className="font-mono text-sm font-bold text-text-primary">{name}</div>
        <div className="font-mono text-xs text-text-muted mt-0.5">
          Anthropic Claude Code · {cfg.model}
        </div>
      </div>
      <p className="font-mono text-xs text-text-muted/60 leading-relaxed">{cfg.brief}</p>
      <div className="grid grid-cols-3 gap-2 pt-1 border-t border-border-dim">
        {[
          { label: "TOOLS",  value: String(telemetry.tools) },
          { label: "TOKENS", value: fmtNum(telemetry.tokens) },
          { label: "COST",   value: fmtUsd(telemetry.usd) },
        ].map(s => (
          <div key={s.label} className="text-center pt-2">
            <div className="font-mono text-sm font-bold text-text-primary">
              <FlashValue value={s.value} />
            </div>
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
          <div className="flex items-center gap-2 mt-3">
            <GlobeIcon />
            <span className="font-mono text-xs text-text-muted">{envId}</span>
          </div>
          <div className="font-mono text-xs text-text-muted/40 mt-1 pl-[18px]">
            ghcr.io/diogobaltazar/topgun/agent:latest
          </div>
        </div>
        <div className="text-right shrink-0 ml-6">
          <div className="font-mono text-3xl font-bold text-amber-tac tabular-nums">{fmtElapsed(elapsed)}</div>
          <div className="font-mono text-xs text-text-muted mt-1 tracking-widest">ELAPSED</div>
        </div>
      </div>

      {/* Mission totals */}
      <div className="grid grid-cols-3 gap-3 px-6 py-4 border-b border-border-dim">
        {[
          { label: "TOTAL TOOLS",  value: String(totalTools) },
          { label: "TOTAL TOKENS", value: fmtNum(totalTokens) },
          { label: "TOTAL COST",   value: fmtUsd(totalUsd) },
        ].map(s => (
          <div key={s.label} className="border border-border-dim p-3 text-center">
            <div className="font-mono text-base font-bold text-amber-tac">
              <FlashValue value={s.value} />
            </div>
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
        <button
          onClick={() => abort(mission.uid)}
          className="font-mono text-xs px-4 py-1.5 border border-red-alert text-red-alert hover:bg-red-alert/10 tracking-widest"
        >
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
