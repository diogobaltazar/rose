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

// ── Static config ─────────────────────────────────────────────────────────────

const PILOT_NAMES = ["MAVERICK", "ICEMAN", "ROOSTER", "PHOENIX", "HANGMAN", "BOB"];

const CREW_CONFIG = [
  { role: "TEAM LEAD",  model: "Opus 4.5",   tokRate: 0.000015, toolsPerTick: [2, 4], tokPerTick: [800, 1800] },
  { role: "WINGMAN",   model: "Sonnet 4.5",  tokRate: 0.000003, toolsPerTick: [1, 3], tokPerTick: [400, 1200] },
];

function pickPilots(uid: string): [string, string] {
  const hash = uid.split("").reduce((a, c) => a + c.charCodeAt(0), 0);
  const lead = PILOT_NAMES[hash % PILOT_NAMES.length];
  const wingman = PILOT_NAMES[(hash + 2) % PILOT_NAMES.length];
  return [lead, wingman === lead ? PILOT_NAMES[(hash + 3) % PILOT_NAMES.length] : wingman];
}

function rand(min: number, max: number) { return Math.floor(Math.random() * (max - min + 1)) + min; }

// ── Globe SVG (white, transparent bg) ────────────────────────────────────────

function GlobeIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.5" strokeLinecap="round">
      <circle cx="12" cy="12" r="10" />
      <ellipse cx="12" cy="12" rx="4" ry="10" />
      <line x1="2" y1="12" x2="22" y2="12" />
      <line x1="12" y1="2" x2="12" y2="4" />
      <line x1="12" y1="20" x2="12" y2="22" />
    </svg>
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
    <div className="border border-border-dim p-4 space-y-3 animate-fadeIn flex-1">
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
      <div className="grid grid-cols-3 gap-2 pt-1">
        {[
          { label: "TOOLS", value: String(telemetry.tools) },
          { label: "TOKENS", value: fmtNum(telemetry.tokens) },
          { label: "COST", value: fmtUsd(telemetry.usd) },
        ].map(s => (
          <div key={s.label} className="text-center">
            <div className="font-mono text-sm font-bold text-text-primary tabular-nums">{s.value}</div>
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
  const [pilots] = useState(() => pickPilots(mission.uid));

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
        const addTools = rand(...cfg.toolsPerTick as [number, number]);
        const addTok = rand(...cfg.tokPerTick as [number, number]);
        const tools = p.tools + addTools;
        const tokens = p.tokens + addTok;
        return { tools, tokens, usd: tokens * cfg.tokRate };
      }) as TelArr);
    }, 2500);
    return () => clearInterval(tick);
  }, []);

  const totalTools = telemetry[0].tools + telemetry[1].tools;
  const totalTokens = telemetry[0].tokens + telemetry[1].tokens;
  const totalUsd = telemetry[0].usd + telemetry[1].usd;
  const envId = `workspace-tgun-${mission.uid.slice(0, 6)}.gitpod.io`;

  return (
    <div className="tac-border animate-fadeIn">
      {/* Mission header */}
      <div className="flex items-start justify-between px-6 py-5 border-b border-border-dim">
        <div>
          <div className="font-mono text-xs text-amber-tac tracking-[0.3em] uppercase mb-1">Active Mission</div>
          <div className="font-mono text-sm font-bold text-text-primary leading-snug">{mission.title}</div>
          <div className="font-mono text-xs text-text-muted mt-1">{mission.uid}</div>
          {/* ONA environment (mission-level) */}
          <div className="flex items-center gap-2 mt-3">
            <GlobeIcon />
            <span className="font-mono text-xs text-text-muted">{envId}</span>
          </div>
          <div className="font-mono text-xs text-text-muted/50 mt-1 pl-[18px]">
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
          { label: "TOTAL TOOLS", value: String(totalTools) },
          { label: "TOTAL TOKENS", value: fmtNum(totalTokens) },
          { label: "TOTAL COST", value: fmtUsd(totalUsd) },
        ].map(s => (
          <div key={s.label} className="border border-border-dim p-3 text-center">
            <div className="font-mono text-base font-bold text-amber-tac tabular-nums">{s.value}</div>
            <div className="font-mono text-xs text-text-muted tracking-widest mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Crew */}
      <div className="px-6 py-4">
        <div className="font-mono text-xs text-text-muted tracking-widest uppercase mb-3">Crew</div>
        <div className="flex gap-3">
          {CREW_CONFIG.map((cfg, i) => (
            <PilotCard key={i} cfg={cfg} name={pilots[i]} telemetry={telemetry[i]} />
          ))}
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
