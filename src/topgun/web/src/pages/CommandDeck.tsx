import { useState, useEffect, useCallback } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useToken } from "../hooks/useToken";
import NavBar from "../components/NavBar";
import HUDGrid from "../components/HUDGrid";
import { getIntelStats, getIntelList, searchIntel } from "../api";
import type { IntelStats, IntelDocument, IntelSearchResult } from "../types";

type Tab = "missions" | "intel";
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
          {(["missions", "intel"] as Tab[]).map((t) => (
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

        {/* View toggle + Search */}
        <div className="flex items-center gap-4 mb-8">
          <div className="flex items-center gap-0 border border-border-dim w-fit">
            {(["stats", "cards"] as View[]).map((v) => (
              <button
                key={v}
                onClick={() => setView(v)}
                className={`font-mono text-xs px-4 py-1.5 tracking-widest uppercase transition-colors
                  ${view === v
                    ? "bg-card text-amber-tac"
                    : "text-text-muted hover:text-text-secondary"
                  }`}
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
            <button
              onClick={handleSearch}
              className="font-mono text-xs px-4 py-1.5 border border-border-dim text-amber-tac hover:bg-card tracking-widest"
            >
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
              <div className="space-y-2">
                {searchResults.map((r) => (
                  <IntelCard key={r.uid} uid={r.uid} source={r.source} sourceUrl={r.source_url} title={r.title} />
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
    <div className="space-y-2">
      {docs.map((doc) => (
        <IntelCard key={doc.uid} uid={doc.uid} source={doc.source} sourceUrl={doc.source_url} />
      ))}
    </div>
  );
}


function IntelCard({ uid, source, sourceUrl, title }: { uid: string; source: string; sourceUrl: string; title?: string }) {
  const handleClick = () => {
    if (source === "github" && sourceUrl) {
      window.open(sourceUrl, "_blank");
    } else if (source === "obsidian" && sourceUrl) {
      window.open(`obsidian://open?path=${encodeURIComponent(sourceUrl)}`, "_blank");
    }
  };

  return (
    <button
      onClick={handleClick}
      className="w-full text-left tac-border p-4 hover:bg-card-hover transition-colors flex items-center gap-4"
    >
      <div className={`font-mono text-xs px-2 py-0.5 border tracking-widest uppercase ${
        source === "github" ? "border-green-live text-green-live" : "border-cyan-hud text-cyan-hud"
      }`}>
        {source === "github" ? "GH" : "OBS"}
      </div>
      <div className="flex-1 min-w-0">
        <div className="font-mono text-xs text-text-primary truncate">
          {title || sourceUrl || uid}
        </div>
        <div className="font-mono text-xs text-text-muted truncate mt-0.5">
          {uid}
        </div>
      </div>
    </button>
  );
}
