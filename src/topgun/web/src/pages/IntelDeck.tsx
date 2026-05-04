import { useState, useEffect, useCallback } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useToken } from "../hooks/useToken";
import NavBar from "../components/NavBar";
import HUDGrid from "../components/HUDGrid";
import { getIntelStats, getIntelList, searchIntel, peekCache } from "../api";
import { Spinner } from "./MissionDeck";
import type { IntelStats, IntelDocument, IntelSearchResult } from "../types";
import { StatCard, IntelGrid } from "./MissionDeck";

type View = "stats" | "cards";

export default function IntelDeck() {
  const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();
  const { getToken } = useToken();
  const [view, setView] = useState<View>("stats");
  const [stats, setStats] = useState<IntelStats | null>(() => peekCache<IntelStats>("intel-stats"));
  const [docs, setDocs] = useState<IntelDocument[]>(() => peekCache<IntelDocument[]>("intel-list") ?? []);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<IntelSearchResult[] | null>(null);
  const [_loading, setLoading] = useState<boolean>(() => peekCache("intel-stats") === null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) loginWithRedirect();
  }, [isAuthenticated, isLoading, loginWithRedirect]);

  const fetchStats = useCallback(async () => {
    try {
      const token = await getToken();
      setStats(await getIntelStats(token));
    } catch (e) { setError(String(e)); }
    finally { setLoading(false); }
  }, [getToken]);

  const fetchCards = useCallback(async () => {
    try {
      const token = await getToken();
      setDocs(await getIntelList(token));
    } catch (e) { setError(String(e)); }
  }, [getToken]);

  useEffect(() => { if (isAuthenticated) fetchStats(); }, [isAuthenticated, fetchStats]);
  useEffect(() => { if (view === "cards" && isAuthenticated) fetchCards(); }, [view, isAuthenticated, fetchCards]);

  const handleSearch = async () => {
    if (!searchQuery.trim()) { setSearchResults(null); return; }
    try {
      const token = await getToken();
      setSearchResults(await searchIntel(token, searchQuery));
    } catch (e) { setError(String(e)); }
  };

  if (isLoading || (!isAuthenticated && !error)) {
    return <div className="min-h-screen bg-base flex items-center justify-center">
      <span className="font-mono text-xs text-amber-tac animate-pulse_amber tracking-widest">LOADING...</span>
    </div>;
  }

  return (
    <div className="min-h-screen bg-base text-text-primary">
      <HUDGrid />
      <NavBar />
      <main className="relative z-10 max-w-6xl mx-auto px-6 py-10">
        <div className="flex items-end justify-between mb-8">
          <div>
            <div className="font-mono text-xs text-amber-tac tracking-[0.4em] uppercase mb-1">Command Deck</div>
            <h1 className="font-mono text-xl font-semibold text-text-primary">Intel</h1>
            <p className="font-mono text-xs text-text-muted mt-1">All registered intelligence documents</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="flex gap-2">
              <input type="text" value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                placeholder="Search intel..."
                className="bg-card border border-border-dim px-3 py-1.5 font-mono text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-amber-tac w-48"
              />
              <button onClick={handleSearch}
                className="font-mono text-xs px-3 py-1.5 border border-border-dim text-amber-tac hover:bg-card tracking-widest">
                SEARCH
              </button>
            </div>
            <div className="flex items-center gap-0 border border-border-dim">
              {(["stats", "cards"] as View[]).map((v) => (
                <button key={v} onClick={() => setView(v)}
                  className={`font-mono text-xs px-4 py-1.5 tracking-widest uppercase transition-colors ${
                    view === v ? "bg-card text-amber-tac" : "text-text-muted hover:text-text-secondary"
                  }`}>{v}</button>
              ))}
            </div>
          </div>
        </div>

        {error && <div className="tac-border p-6 text-center mb-6">
          <p className="font-mono text-xs text-red-alert tracking-widest">ERROR</p>
          <p className="font-mono text-xs text-text-muted mt-1">{error}</p>
        </div>}

        {searchResults !== null && (
          <div className="mb-8">
            <div className="font-mono text-xs text-text-muted tracking-widest mb-4">
              SEARCH — {searchResults.length} FOUND
            </div>
            <IntelGrid docs={searchResults.map(r => ({ uid: r.uid, source: r.source, source_url: r.source_url, title: r.title } as IntelDocument & { title: string }))} />
          </div>
        )}

        {searchResults === null && view === "stats" && (_loading ? <Spinner /> : stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            {[
              { label: "TOTAL", value: stats.total },
              { label: "GITHUB", value: stats.by_source.github },
              { label: "OBSIDIAN", value: stats.by_source.obsidian },
              { label: "MISSIONS", value: stats.missions },
            ].map((s, i) => <StatCard key={s.label} label={s.label} value={s.value} index={i} />)}
          </div>
        ))}

        {searchResults === null && view === "cards" && <IntelGrid docs={docs} />}
      </main>
    </div>
  );
}
