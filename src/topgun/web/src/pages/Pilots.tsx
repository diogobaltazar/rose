import { useState } from "react";
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

export default function Pilots() {
  const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();

  if (!isLoading && !isAuthenticated) { loginWithRedirect(); return null; }

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
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {PILOTS.map((p) => <PilotCard key={p.callsign} pilot={p} />)}
        </div>
      </main>
    </div>
  );
}

function PilotCard({ pilot }: { pilot: Pilot }) {
  const [open, setOpen] = useState(false);
  const [missionsOpen, setMissionsOpen] = useState(false);

  return (
    <div className="tac-border flex flex-col">
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center justify-between px-5 py-4 hover:bg-card transition-colors text-left"
      >
        <div>
          <div className="font-mono text-sm font-bold text-amber-tac tracking-widest">{pilot.callsign}</div>
          <div className="font-mono text-xs text-text-muted mt-0.5">
            <span className="text-green-live">{pilot.accomplished}W</span>
            {" · "}
            <span className={pilot.failed > 0 ? "text-red-alert" : "text-text-muted"}>{pilot.failed}L</span>
          </div>
        </div>
        <span className="font-mono text-xs text-text-muted">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="border-t border-border-dim px-5 py-4 space-y-4">
          <div className="grid grid-cols-3 gap-2 text-center">
            {[
              { label: "TOKENS", value: fmt(pilot.tokens) },
              { label: "TOOLS", value: fmt(pilot.tools) },
              { label: "COST", value: `$${pilot.usd.toFixed(1)}` },
            ].map((s) => (
              <div key={s.label}>
                <div className="font-mono text-sm font-bold text-text-primary">{s.value}</div>
                <div className="font-mono text-xs text-text-muted tracking-widest">{s.label}</div>
              </div>
            ))}
          </div>

          {pilot.missions.length > 0 && (
            <div>
              <button
                onClick={() => setMissionsOpen((v) => !v)}
                className="font-mono text-xs text-text-muted hover:text-amber-tac tracking-widest uppercase transition-colors"
              >
                MISSIONS ({pilot.missions.length}) {missionsOpen ? "▲" : "▼"}
              </button>

              {missionsOpen && (
                <div className="mt-3 space-y-2">
                  {pilot.missions.map((m) => (
                    <div key={m.uid} className="border border-border-dim p-3">
                      <div className="flex items-start justify-between gap-2 mb-2">
                        <span className="font-mono text-xs text-text-primary leading-snug">{m.title}</span>
                        <span className="font-mono text-xs text-text-muted border border-border-dim px-1.5 py-0.5 shrink-0 tracking-widest uppercase whitespace-nowrap">
                          {m.role}
                        </span>
                      </div>
                      <div className="flex gap-4">
                        <span className="font-mono text-xs text-text-muted">{fmt(m.tokens)} tok</span>
                        <span className="font-mono text-xs text-text-muted">{m.tools} tools</span>
                        <span className="font-mono text-xs text-text-muted">${m.usd.toFixed(2)}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
