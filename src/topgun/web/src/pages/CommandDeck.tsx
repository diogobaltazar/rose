import { useState, useEffect, useCallback } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useToken } from "../hooks/useToken";
import NavBar from "../components/NavBar";
import HUDGrid from "../components/HUDGrid";
import { getIntelStats, getIntelList, searchIntel } from "../api";
import type { IntelStats, IntelDocument, IntelSearchResult } from "../types";

type Tab = "missions" | "intel" | "pilots";
type View = "stats" | "cards";

export default function CommandDeck() {
  const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();
  const { getToken } = useToken();
  const [tab, setTab] = useState<Tab>("missions");
  const [view, setView] = useState<View>("stats");
  const [stats, setStats] = useState<IntelStats | null>(null);
  const [docs, setDocs] = useState<IntelDocument[]>([]);
  const [searchResults, setSearchResults] = useState<IntelSearchResult[] | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      loginWithRedirect();
    }
  }, [isAuthenticated, isLoading, loginWithRedirect]);

  const fetchStats = useCallback(async () => {
    try {
      let token = "";
      token = await getToken();
      const data = await getIntelStats(token);
      setStats(data);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }, [getToken]);

  useEffect(() => {
    if (isAuthenticated) fetchStats();
  }, [isAuthenticated, fetchStats]);

  const fetchCards = useCallback(async () => {
    try {
      let token = "";
      token = await getToken();
      const data = await getIntelList(token);
      setDocs(data);
    } catch (e) {
      setError(String(e));
    }
  }, [getToken]);

  useEffect(() => {
    if (view === "cards" && isAuthenticated) fetchCards();
  }, [view, isAuthenticated, fetchCards]);

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchResults(null);
      return;
    }
    try {
      let token = "";
      token = await getToken();
      const results = await searchIntel(token, searchQuery);
      setSearchResults(results);
    } catch (e) {
      setError(String(e));
    }
  };

  if (isLoading || (!isAuthenticated && !error)) {
    return (
      <div className="min-h-screen bg-base flex items-center justify-center">
        <span className="font-mono text-xs text-amber-tac animate-pulse_amber tracking-widest">
          LOADING...
        </span>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-base text-text-primary">
      <HUDGrid />
      <NavBar />

      <main className="relative z-10 max-w-5xl mx-auto px-6 py-10">
        {/* Header */}
        <div className="flex items-end justify-between mb-8">
          <div>
            <div className="font-mono text-xs text-amber-tac tracking-[0.4em] uppercase mb-1">
              Command Deck
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex items-center gap-0 mb-6 border border-border-dim w-fit">
          {(["missions", "intel", "pilots"] as Tab[]).map((t) => (
            <button
              key={t}
              onClick={() => { setTab(t); setSearchResults(null); }}
              className={`font-mono text-xs px-5 py-2 tracking-widest uppercase transition-colors
                ${tab === t
                  ? "bg-amber-tac text-base"
                  : "text-text-secondary hover:text-amber-tac hover:bg-card"
                }`}
            >
              {t}
            </button>
          ))}
        </div>

        {/* Pilots tab */}
        {tab === "pilots" && <PilotsPanel />}

        {/* Intel / Missions tabs */}
        {tab !== "pilots" && (
          <>
            {/* View toggle + Search */}
            <div className="flex items-center gap-4 mb-8">
              <div className="flex items-center gap-0 border border-border-dim w-fit">
                {(["stats", "cards"] as View[]).map((v) => (
                  <button
                    key={v}
                    onClick={() => setView(v)}
                    className={`font-mono text-xs px-4 py-1.5 tracking-widest uppercase transition-colors
                      ${view === v ? "bg-card text-amber-tac" : "text-text-muted hover:text-text-secondary"}`}
                  >
                    {v}
                  </button>
                ))}
              </div>
              <div className="flex-1 flex gap-2">
                <input
                  type="text"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                  placeholder="Search intel..."
                  className="flex-1 bg-card border border-border-dim px-3 py-1.5 font-mono text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-amber-tac"
                />
                <button onClick={handleSearch} className="font-mono text-xs px-4 py-1.5 border border-border-dim text-amber-tac hover:bg-card tracking-widest">
                  SEARCH
                </button>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="tac-border p-6 text-center mb-6">
                <p className="font-mono text-xs text-red-alert tracking-widest">ERROR</p>
                <p className="font-mono text-xs text-text-muted mt-1">{error}</p>
              </div>
            )}

            {/* Search Results */}
            {searchResults !== null && (
              <div className="mb-8">
                <div className="font-mono text-xs text-text-muted tracking-widest mb-4">
                  SEARCH RESULTS — {searchResults.length} FOUND
                </div>
                {searchResults.length === 0 ? (
                  <div className="tac-border p-6 text-center">
                    <p className="font-mono text-xs text-text-muted">NO MATCHES</p>
                  </div>
                ) : (
                  <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                    {searchResults.map((r) => (
                      <IntelCard key={r.uid} doc={{ uid: r.uid, source: r.source, source_url: r.source_url, title: r.title }} />
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Stats View */}
            {searchResults === null && view === "stats" && (
              <StatsPanel stats={stats} loading={loading} tab={tab} />
            )}

            {/* Cards View */}
            {searchResults === null && view === "cards" && (
              <CardsPanel docs={docs} tab={tab} />
            )}
          </>
        )}
      </main>
    </div>
  );
}


function StatsPanel({ stats, loading, tab }: { stats: IntelStats | null; loading: boolean; tab: Tab }) {
  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <span className="font-mono text-xs text-amber-tac animate-pulse_amber tracking-widest">
          COMPUTING STATS...
        </span>
      </div>
    );
  }
  if (!stats) return null;

  const statItems = tab === "missions"
    ? [
        { label: "MISSIONS", value: stats.missions },
        { label: "DRAFTS", value: stats.drafts },
        { label: "READY", value: stats.ready },
      ]
    : [
        { label: "TOTAL INTEL", value: stats.total },
        { label: "GITHUB", value: stats.by_source.github },
        { label: "OBSIDIAN", value: stats.by_source.obsidian },
        { label: "MISSIONS", value: stats.missions },
      ];

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
      {statItems.map((s) => (
        <div key={s.label} className="tac-border p-6 text-center bracket-corners">
          <div className="font-mono text-2xl font-bold text-amber-tac">{s.value}</div>
          <div className="font-mono text-xs text-text-muted tracking-widest mt-2">{s.label}</div>
        </div>
      ))}
    </div>
  );
}


function CardsPanel({ docs, tab }: { docs: IntelDocument[]; tab: Tab }) {
  const label = tab === "missions" ? "MISSIONS" : "INTEL DOCUMENTS";
  if (docs.length === 0) {
    return (
      <div className="tac-border p-12 text-center bracket-corners">
        <p className="font-mono text-xs text-text-muted tracking-widest">NO {label}</p>
        <p className="font-mono text-xs text-text-muted/60 mt-2">
          Create intel or track existing documents to populate this view.
        </p>
      </div>
    );
  }

  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
      {docs.map((doc) => (
        <IntelCard key={doc.uid} doc={doc} />
      ))}
    </div>
  );
}


function IntelCard({ doc }: { doc: IntelDocument & { title?: string; tags?: string[]; auto_discovered?: boolean } }) {
  const { uid, source, source_url: sourceUrl } = doc;
  const title = (doc as { title?: string }).title || sourceUrl?.split("/").pop()?.replace(".md", "") || uid;

  // Derive mission status from tags (fetched lazily — currently placeholder)
  const tags: string[] = (doc as { tags?: string[] }).tags ?? [];
  const isMission = tags.includes("topgun-mission");
  const isReady = tags.includes("topgun-mission-ready");

  const openSource = () => {
    if (source === "github" && sourceUrl) window.open(sourceUrl, "_blank");
    else if (source === "obsidian" && sourceUrl)
      const parts = sourceUrl.replace(/^vault\//, "").split("/");
      const vault = "vault";
      const file = parts.join("/").replace(/\.md$/, "");
      window.open(`obsidian://open?vault=${encodeURIComponent(vault)}&file=${encodeURIComponent(file)}`, "_blank");
  };

  return (
    <div className="tac-border flex flex-col aspect-square p-4 hover:bg-card transition-colors">
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <span className={`font-mono text-xs px-1.5 py-0.5 border tracking-widest ${
          source === "github" ? "border-green-live text-green-live" : "border-cyan-hud text-cyan-hud"
        }`}>
          {source === "github" ? "GH" : "OBS"}
        </span>
        <span className="font-mono text-xs text-text-muted/40">{uid.slice(0, 6)}</span>
      </div>

      {/* Title */}
      <button
        onClick={openSource}
        className="flex-1 text-left font-mono text-xs text-text-primary leading-relaxed hover:text-amber-tac transition-colors line-clamp-4"
      >
        {title}
      </button>

      {/* Action button */}
      <div className="mt-3">
        {isMission ? (
          <button className={`w-full font-mono text-xs py-1.5 tracking-widest border transition-colors ${
            isReady
              ? "border-green-live text-green-live hover:bg-green-live/10"
              : "border-amber-tac text-amber-tac hover:bg-amber-tac/10"
          }`}>
            {isReady ? "→ ENGAGE" : "→ PLAN"}
          </button>
        ) : (
          <button
            onClick={openSource}
            className="w-full font-mono text-xs py-1.5 tracking-widest border border-border-dim text-text-muted hover:text-text-secondary hover:border-text-muted transition-colors"
          >
            → OPEN
          </button>
        )}
      </div>
    </div>
  );
}

// ── Pilots ────────────────────────────────────────────────────────────────────

interface PilotMission {
  uid: string;
  title: string;
  role: string;
  tokens: number;
  tools: number;
  usd: number;
}

interface Pilot {
  callsign: string;
  accomplished: number;
  failed: number;
  tokens: number;
  tools: number;
  usd: number;
  missions: PilotMission[];
}

const MOCK_PILOTS: Pilot[] = [
  {
    callsign: "MAVERICK",
    accomplished: 14, failed: 1, tokens: 2_840_000, tools: 1_203, usd: 28.4,
    missions: [
      { uid: "a1b2c3", title: "Refactor auth middleware", role: "Team Lead", tokens: 420_000, tools: 180, usd: 4.2 },
      { uid: "d4e5f6", title: "Fix payment race condition", role: "Team Lead", tokens: 310_000, tools: 140, usd: 3.1 },
      { uid: "g7h8i9", title: "Add rate limiting", role: "Team Lead", tokens: 280_000, tools: 95, usd: 2.8 },
    ],
  },
  {
    callsign: "ICEMAN",
    accomplished: 11, failed: 0, tokens: 1_960_000, tools: 890, usd: 19.6,
    missions: [
      { uid: "j1k2l3", title: "Refactor auth middleware", role: "Wingman", tokens: 210_000, tools: 88, usd: 2.1 },
      { uid: "m4n5o6", title: "Migrate database schema", role: "Team Lead", tokens: 380_000, tools: 165, usd: 3.8 },
    ],
  },
  {
    callsign: "ROOSTER",
    accomplished: 8, failed: 2, tokens: 1_420_000, tools: 612, usd: 14.2,
    missions: [
      { uid: "p7q8r9", title: "Add rate limiting", role: "Wingman", tokens: 190_000, tools: 72, usd: 1.9 },
      { uid: "s1t2u3", title: "Deploy monitoring stack", role: "Team Lead", tokens: 270_000, tools: 110, usd: 2.7 },
    ],
  },
  {
    callsign: "PHOENIX",
    accomplished: 9, failed: 1, tokens: 1_680_000, tools: 740, usd: 16.8,
    missions: [
      { uid: "v4w5x6", title: "Fix payment race condition", role: "Wingman", tokens: 155_000, tools: 62, usd: 1.55 },
    ],
  },
  {
    callsign: "HANGMAN",
    accomplished: 6, failed: 0, tokens: 980_000, tools: 420, usd: 9.8,
    missions: [
      { uid: "y7z8a9", title: "Deploy monitoring stack", role: "Wingman", tokens: 130_000, tools: 55, usd: 1.3 },
    ],
  },
  {
    callsign: "BOB",
    accomplished: 7, failed: 1, tokens: 1_120_000, tools: 510, usd: 11.2,
    missions: [],
  },
];

function fmt(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

function PilotsPanel() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      {MOCK_PILOTS.map((p) => <PilotCard key={p.callsign} pilot={p} />)}
    </div>
  );
}

function PilotCard({ pilot }: { pilot: Pilot }) {
  const [open, setOpen] = useState(false);
  const [missionsOpen, setMissionsOpen] = useState(false);

  return (
    <div className="tac-border flex flex-col">
      {/* Header — always visible */}
      <button
        onClick={() => setOpen((v) => !v)}
        className="flex items-center justify-between px-5 py-4 hover:bg-card transition-colors text-left"
      >
        <div>
          <div className="font-mono text-sm font-bold text-amber-tac tracking-widest">{pilot.callsign}</div>
          <div className="font-mono text-xs text-text-muted mt-0.5">
            {pilot.accomplished}W · {pilot.failed}L
          </div>
        </div>
        <span className="font-mono text-xs text-text-muted">{open ? "▲" : "▼"}</span>
      </button>

      {/* Expanded stats */}
      {open && (
        <div className="border-t border-border-dim px-5 py-4 space-y-3">
          {/* Summary stats */}
          <div className="grid grid-cols-3 gap-2">
            {[
              { label: "TOKENS", value: fmt(pilot.tokens) },
              { label: "TOOLS", value: fmt(pilot.tools) },
              { label: "COST", value: `$${pilot.usd.toFixed(1)}` },
            ].map((s) => (
              <div key={s.label} className="text-center">
                <div className="font-mono text-sm font-bold text-text-primary">{s.value}</div>
                <div className="font-mono text-xs text-text-muted tracking-widest">{s.label}</div>
              </div>
            ))}
          </div>

          {/* Missions toggle */}
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
                        <span className="font-mono text-xs text-text-muted border border-border-dim px-1.5 py-0.5 shrink-0 tracking-widest uppercase">
                          {m.role.split(" ")[1] ?? m.role}
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
