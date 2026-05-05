import { useState, useMemo } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import NavBar from "../components/NavBar";
import HUDGrid from "../components/HUDGrid";

interface PilotMission {
  uid: string; title: string; role: string;
  tokens: number; tools: number; usd: number;
}
interface Pilot {
  callsign: string; accomplished: number; failed: number;
  tokens: number; tools: number; usd: number;
  missions: PilotMission[];
  isUser?: boolean;
}

const PILOTS: Pilot[] = [
  {
    callsign: "MAVERICK", accomplished: 14, failed: 1,
    tokens: 2_840_000, tools: 1_203, usd: 28.4,
    missions: [
      { uid: "a1b2c3", title: "Refactor auth middleware", role: "Team Lead", tokens: 420_000, tools: 180, usd: 4.2 },
      { uid: "d4e5f6", title: "Fix payment race condition", role: "Team Lead", tokens: 310_000, tools: 140, usd: 3.1 },
      { uid: "g7h8i9", title: "Add rate limiting", role: "Team Lead", tokens: 280_000, tools: 95, usd: 2.8 },
    ],
  },
  {
    callsign: "ICEMAN", accomplished: 11, failed: 0,
    tokens: 1_960_000, tools: 890, usd: 19.6,
    missions: [
      { uid: "j1k2l3", title: "Refactor auth middleware", role: "Wingman", tokens: 210_000, tools: 88, usd: 2.1 },
      { uid: "m4n5o6", title: "Migrate database schema", role: "Team Lead", tokens: 380_000, tools: 165, usd: 3.8 },
    ],
  },
  {
    callsign: "ROOSTER", accomplished: 8, failed: 2,
    tokens: 1_420_000, tools: 612, usd: 14.2,
    missions: [
      { uid: "p7q8r9", title: "Add rate limiting", role: "Wingman", tokens: 190_000, tools: 72, usd: 1.9 },
      { uid: "s1t2u3", title: "Deploy monitoring stack", role: "Team Lead", tokens: 270_000, tools: 110, usd: 2.7 },
    ],
  },
  {
    callsign: "PHOENIX", accomplished: 9, failed: 1,
    tokens: 1_680_000, tools: 740, usd: 16.8,
    missions: [
      { uid: "v4w5x6", title: "Fix payment race condition", role: "Wingman", tokens: 155_000, tools: 62, usd: 1.55 },
    ],
  },
  {
    callsign: "HANGMAN", accomplished: 6, failed: 0,
    tokens: 980_000, tools: 420, usd: 9.8,
    missions: [
      { uid: "y7z8a9", title: "Deploy monitoring stack", role: "Wingman", tokens: 130_000, tools: 55, usd: 1.3 },
    ],
  },
  {
    callsign: "BOB", accomplished: 7, failed: 1,
    tokens: 1_120_000, tools: 510, usd: 11.2,
    missions: [],
  },
];

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

function Mugshot({ callsign, size = "sm" }: { callsign: string; size?: "sm" | "lg" }) {
  const dim = size === "sm" ? "w-10 h-10" : "w-20 h-20";
  const textSize = size === "sm" ? "text-base" : "text-3xl";
  return (
    <div className={`${dim} relative border border-amber-tac/25 bg-card flex items-center justify-center shrink-0 overflow-hidden`}>
      <div className="absolute inset-0">
        <div className="absolute top-1/2 left-0 right-0 h-px bg-amber-tac/10" />
        <div className="absolute left-1/2 top-0 bottom-0 w-px bg-amber-tac/10" />
      </div>
      <div className="absolute top-0 left-0 w-2 h-2 border-t border-l border-amber-tac/35" />
      <div className="absolute top-0 right-0 w-2 h-2 border-t border-r border-amber-tac/35" />
      <div className="absolute bottom-0 left-0 w-2 h-2 border-b border-l border-amber-tac/35" />
      <div className="absolute bottom-0 right-0 w-2 h-2 border-b border-r border-amber-tac/35" />
      <span className={`font-mono ${textSize} font-bold text-amber-tac/50 relative z-10`}>{callsign[0]}</span>
    </div>
  );
}

function PilotCardCompact({ pilot, onClick, index }: { pilot: Pilot; onClick: () => void; index: number }) {
  return (
    <button
      onClick={onClick}
      className="tac-border flex items-center gap-4 px-4 py-3 hover:bg-card transition-colors text-left w-full animate-fadeIn"
      style={{ animationDelay: `${index * 0.06}s` }}
    >
      <Mugshot callsign={pilot.callsign} size="sm" />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-mono text-sm font-bold text-amber-tac tracking-widest">{pilot.callsign}</span>
          {pilot.isUser && (
            <span className="font-mono text-xs border border-amber-tac text-amber-tac px-1.5 py-0.5 tracking-widest leading-none">YOU</span>
          )}
        </div>
        <div className="font-mono text-xs text-text-muted mt-0.5">
          <span className="text-green-live">{pilot.accomplished}W</span>
          {" · "}
          <span className={pilot.failed > 0 ? "text-red-alert" : "text-text-muted"}>{pilot.failed}L</span>
          {pilot.isUser && pilot.accomplished === 0 && (
            <span className="ml-2 text-text-muted/40">via daemon</span>
          )}
        </div>
      </div>
      <span className="font-mono text-xs text-text-muted/40">▶</span>
    </button>
  );
}

function PilotCardExpanded({ pilot, onClose }: { pilot: Pilot; onClose: () => void }) {
  const [missionsOpen, setMissionsOpen] = useState(false);

  return (
    <div className={`tac-border animate-fadeIn ${pilot.isUser ? "border-amber-tac" : ""}`}>
      {/* header */}
      <div className="flex items-start gap-6 px-6 py-5 border-b border-border-dim">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 mb-3">
            <span className="font-mono text-lg font-bold text-amber-tac tracking-widest">{pilot.callsign}</span>
            {pilot.isUser && (
              <span className="font-mono text-xs border border-amber-tac text-amber-tac px-1.5 py-0.5 tracking-widest">YOU</span>
            )}
            <span className="font-mono text-xs text-text-muted ml-auto">
              <span className="text-green-live">{pilot.accomplished}W</span>
              {" · "}
              <span className={pilot.failed > 0 ? "text-red-alert" : "text-text-muted"}>{pilot.failed}L</span>
            </span>
          </div>
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: "TOKENS", value: fmt(pilot.tokens) },
              { label: "TOOLS", value: fmt(pilot.tools) },
              { label: "COST", value: `$${pilot.usd.toFixed(1)}` },
            ].map((s) => (
              <div key={s.label}>
                <div className="font-mono text-base font-bold text-text-primary">{s.value}</div>
                <div className="font-mono text-xs text-text-muted tracking-widest mt-0.5">{s.label}</div>
              </div>
            ))}
          </div>
        <button
          onClick={onClose}
          className="font-mono text-xs text-text-muted hover:text-amber-tac transition-colors tracking-widest shrink-0"
        >
          ✕
        </button>
      </div>

      {/* missions */}
      <div className="px-6 py-4">
        {pilot.missions.length === 0 ? (
          <p className="font-mono text-xs text-text-muted/50 tracking-widest">NO MISSIONS LOGGED</p>
        ) : (
          <>
            <button
              onClick={() => setMissionsOpen(v => !v)}
              className="font-mono text-xs text-text-muted hover:text-amber-tac tracking-widest uppercase transition-colors"
            >
              MISSIONS ({pilot.missions.length}) {missionsOpen ? "▲" : "▼"}
            </button>
            {missionsOpen && (
              <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {pilot.missions.map((m, i) => {
                  const isLead = m.role.toLowerCase().includes("lead");
                  const aircraft = isLead
                    ? "Anthropic Claude Code · Opus 4.5"
                    : "Anthropic Claude Code · Sonnet 4.5";
                  const geo = `workspace-tgun-${m.uid.slice(0, 6)}.gitpod.io`;
                  return (
                  <div
                    key={m.uid}
                    className="border border-border-dim p-3 animate-fadeIn space-y-2"
                    style={{ animationDelay: `${i * 0.05}s` }}
                  >
                    {/* title + role */}
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-mono text-xs text-text-primary leading-snug">{m.title}</span>
                      <span className="font-mono text-xs text-text-muted border border-border-dim px-1.5 py-0.5 shrink-0 tracking-widest uppercase whitespace-nowrap">
                        {m.role}
                      </span>
                    </div>
                    {/* mission id */}
                    <div className="font-mono text-xs text-text-muted/40">{m.uid}</div>
                    {/* aircraft */}
                    <div className="flex items-center gap-1.5">
                      <span className="text-amber-tac/60 text-xs">✈</span>
                      <span className="font-mono text-xs text-text-muted">{aircraft}</span>
                    </div>
                    {/* geography */}
                    <div className="flex items-center gap-1.5">
                      <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.5" strokeLinecap="round" className="opacity-40 shrink-0">
                        <circle cx="12" cy="12" r="10"/><ellipse cx="12" cy="12" rx="4" ry="10"/><line x1="2" y1="12" x2="22" y2="12"/>
                      </svg>
                      <span className="font-mono text-xs text-text-muted/60">{geo}</span>
                    </div>
                    {/* telemetry */}
                    <div className="flex gap-3 pt-1 border-t border-border-dim">
                      <span className="font-mono text-xs text-text-muted">{fmt(m.tokens)} tok</span>
                      <span className="font-mono text-xs text-text-muted">{m.tools} tools</span>
                      <span className="font-mono text-xs text-text-muted">${m.usd.toFixed(2)}</span>
                    </div>
                  </div>
                  );
                })}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}

export default function Pilots() {
  const { isAuthenticated, isLoading, loginWithRedirect, user } = useAuth0();
  const [selected, setSelected] = useState<string | null>(null);

  if (!isLoading && !isAuthenticated) { loginWithRedirect(); return null; }

  const userPilot: Pilot | null = useMemo(() => {
    if (!user) return null;
    const callsign = (user.nickname ?? user.email?.split("@")[0] ?? "you").toUpperCase();
    return { callsign, accomplished: 0, failed: 0, tokens: 0, tools: 0, usd: 0, missions: [], isUser: true };
  }, [user]);

  const allPilots = useMemo(() =>
    userPilot ? [userPilot, ...PILOTS] : PILOTS,
  [userPilot]);

  const selectedIdx = selected ? allPilots.findIndex(p => p.callsign === selected) : -1;
  const selectedPilot = selectedIdx >= 0 ? allPilots[selectedIdx] : null;
  const before = selectedIdx >= 0 ? allPilots.slice(0, selectedIdx) : allPilots;
  const after = selectedIdx >= 0 ? allPilots.slice(selectedIdx + 1) : [];

  const toggle = (callsign: string) => setSelected(v => v === callsign ? null : callsign);

  return (
    <div className="min-h-screen bg-base text-text-primary">
      <HUDGrid />
      <NavBar />
      <main className="relative z-10 max-w-6xl mx-auto px-6 py-10">
        <div className="mb-8">
          <div className="font-mono text-xs text-amber-tac tracking-[0.4em] uppercase mb-1">Command Deck</div>
          <h1 className="font-mono text-xl font-semibold">Pilots</h1>
          <p className="font-mono text-xs text-text-muted mt-1">Pilot roster — mission telemetry and performance</p>
        </div>

        <div className="space-y-4">
          {before.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {before.map((p, i) => (
                <PilotCardCompact key={p.callsign} pilot={p} onClick={() => toggle(p.callsign)} index={i} />
              ))}
            </div>
          )}
          {selectedPilot && (
            <PilotCardExpanded pilot={selectedPilot} onClose={() => setSelected(null)} />
          )}
          {after.length > 0 && (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
              {after.map((p, i) => (
                <PilotCardCompact key={p.callsign} pilot={p} onClick={() => toggle(p.callsign)} index={i} />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
