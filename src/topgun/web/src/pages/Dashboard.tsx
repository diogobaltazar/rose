import { useState, useEffect } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { getMissions } from "../api";
import type { Mission } from "../types";
import NavBar from "../components/NavBar";
import MissionCard from "../components/MissionCard";
import HUDGrid from "../components/HUDGrid";

type Filter = "all" | "open" | "closed";

export default function Dashboard() {
  const { isAuthenticated, isLoading, getAccessTokenSilently, loginWithRedirect } = useAuth0();
  const [missions, setMissions] = useState<Mission[]>([]);
  const [filter, setFilter] = useState<Filter>("open");
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) {
      loginWithRedirect();
    }
  }, [isAuthenticated, isLoading, loginWithRedirect]);

  useEffect(() => {
    if (!isAuthenticated) return;
    (async () => {
      try {
        let token = "";
        try { token = await getAccessTokenSilently(); } catch { /* dev mode */ }
        const data = await getMissions(token);
        setMissions(data);
      } catch (e) {
        setError(String(e));
      } finally {
        setFetching(false);
      }
    })();
  }, [isAuthenticated, getAccessTokenSilently]);

  const filtered = missions.filter((m) => filter === "all" || m.state === filter);

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
            <h1 className="font-mono text-xl font-semibold text-text-primary">Missions</h1>
          </div>
          <div className="font-mono text-xs text-text-muted">
            {filtered.length} / {missions.length}
          </div>
        </div>

        {/* Filter bar */}
        <div className="flex items-center gap-0 mb-8 border border-border-dim w-fit">
          {(["open", "closed", "all"] as Filter[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`font-mono text-xs px-5 py-2 tracking-widest uppercase transition-colors
                ${filter === f
                  ? "bg-amber-tac text-base"
                  : "text-text-secondary hover:text-amber-tac hover:bg-card"
                }`}
            >
              {f}
            </button>
          ))}
        </div>

        {/* Content */}
        {error && (
          <div className="tac-border p-6 text-center">
            <p className="font-mono text-xs text-red-alert tracking-widest">FETCH ERROR</p>
            <p className="font-mono text-xs text-text-muted mt-1">{error}</p>
          </div>
        )}

        {fetching && !error && (
          <div className="flex items-center justify-center py-20">
            <span className="font-mono text-xs text-amber-tac animate-pulse_amber tracking-widest">
              SCANNING BACKLOG...
            </span>
          </div>
        )}

        {!fetching && !error && filtered.length === 0 && (
          <div className="tac-border p-12 text-center bracket-corners">
            <p className="font-mono text-xs text-text-muted tracking-widest">
              NO MISSIONS FOUND
            </p>
            <p className="font-mono text-xs text-text-muted/60 mt-2">
              Label a GitHub issue <span className="text-amber-tac">topgun-mission</span> to add it here.
            </p>
          </div>
        )}

        {!fetching && !error && filtered.length > 0 && (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {filtered.map((m) => (
              <MissionCard key={m.id} mission={m} />
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
