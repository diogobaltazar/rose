import { useEffect, useState } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import NavBar from "../components/NavBar";
import HUDGrid from "../components/HUDGrid";
import { useEngagement, type EngagedMission } from "../context/EngagementContext";

function fmtElapsed(ms: number): string {
  const s = Math.floor(ms / 1000);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

const MOCK_CREW = [
  {
    role: "TEAM LEAD",
    model: "Opus 4.5",
    provider: "Anthropic Claude Code",
    env: "workspace-tgun-a1b2c3.gitpod.io",
    image: "topgun/agent:latest",
  },
  {
    role: "WINGMAN",
    model: "Sonnet 4.5",
    provider: "Anthropic Claude Code",
    env: "workspace-tgun-d4e5f6.gitpod.io",
    image: "topgun/agent:latest",
  },
];

function PilotCard({ pilot }: { pilot: typeof MOCK_CREW[0] }) {
  return (
    <div className="border border-border-dim p-4 space-y-2 animate-fadeIn">
      <div className="flex items-center gap-2 mb-3">
        <span className="text-amber-tac text-base">✈</span>
        <span className="font-mono text-xs text-amber-tac tracking-widest">{pilot.role}</span>
      </div>
      <div className="font-mono text-xs text-text-primary">{pilot.provider}</div>
      <div className="font-mono text-xs text-text-muted">Model · {pilot.model}</div>
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs text-text-muted">🌐</span>
        <span className="font-mono text-xs text-text-muted truncate">{pilot.env}</span>
      </div>
      <div className="font-mono text-xs text-text-muted/50">{pilot.image}</div>
    </div>
  );
}

function MissionCard({ mission }: { mission: EngagedMission }) {
  const { abort } = useEngagement();
  const [elapsed, setElapsed] = useState(Date.now() - mission.startedAt.getTime());

  useEffect(() => {
    const id = setInterval(() => setElapsed(Date.now() - mission.startedAt.getTime()), 1000);
    return () => clearInterval(id);
  }, [mission.startedAt]);

  return (
    <div className="tac-border animate-fadeIn">
      {/* Header */}
      <div className="flex items-start justify-between px-6 py-5 border-b border-border-dim">
        <div>
          <div className="font-mono text-xs text-amber-tac tracking-[0.3em] uppercase mb-1">Active Mission</div>
          <div className="font-mono text-sm font-bold text-text-primary leading-snug">{mission.title}</div>
          <div className="font-mono text-xs text-text-muted mt-1">{mission.uid}</div>
        </div>
        <div className="text-right shrink-0 ml-6">
          <div className="font-mono text-3xl font-bold text-amber-tac tabular-nums">{fmtElapsed(elapsed)}</div>
          <div className="font-mono text-xs text-text-muted mt-1 tracking-widest">ELAPSED</div>
        </div>
      </div>

      {/* Cost placeholders */}
      <div className="grid grid-cols-3 gap-3 px-6 py-4 border-b border-border-dim">
        {[
          { label: "TOOL CALLS", value: "—" },
          { label: "TOKENS", value: "—" },
          { label: "COST", value: "—" },
        ].map(s => (
          <div key={s.label} className="border border-border-dim p-3 text-center">
            <div className="font-mono text-base font-bold text-text-primary">{s.value}</div>
            <div className="font-mono text-xs text-text-muted tracking-widest mt-1">{s.label}</div>
          </div>
        ))}
      </div>

      {/* Crew */}
      <div className="px-6 py-4">
        <div className="font-mono text-xs text-text-muted tracking-widest uppercase mb-3">Crew</div>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
          {MOCK_CREW.map((p, i) => <PilotCard key={i} pilot={p} />)}
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
