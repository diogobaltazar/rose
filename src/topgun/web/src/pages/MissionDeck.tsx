import { useState, useEffect, useCallback } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useToken } from "../hooks/useToken";
import NavBar from "../components/NavBar";
import HUDGrid from "../components/HUDGrid";
import { getIntelStats, getIntelList } from "../api";
import type { IntelStats, IntelDocument } from "../types";

type View = "stats" | "cards";

export default function MissionDeck() {
  const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();
  const { getToken } = useToken();
  const [view, setView] = useState<View>("stats");
  const [stats, setStats] = useState<IntelStats | null>(null);
  const [docs, setDocs] = useState<IntelDocument[]>([]);
  const [loading, setLoading] = useState(true);
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
      // Only missions (topgun-mission tagged) — for now show all, filter by tag when available
      setDocs(await getIntelList(token));
    } catch (e) { setError(String(e)); }
  }, [getToken]);

  useEffect(() => { if (isAuthenticated) fetchStats(); }, [isAuthenticated, fetchStats]);
  useEffect(() => { if (view === "cards" && isAuthenticated) fetchCards(); }, [view, isAuthenticated, fetchCards]);

  if (isLoading || (!isAuthenticated && !error)) {
    return <div className="min-h-screen bg-base flex items-center justify-center">
      <span className="font-mono text-xs text-amber-tac animate-pulse_amber tracking-widest">LOADING...</span>
    </div>;
  }

  const missionStats = stats ? {
    total: stats.missions,
    drafts: stats.drafts,
    ready: stats.ready,
    engaged: 0,
  } : null;

  return (
    <div className="min-h-screen bg-base text-text-primary">
      <HUDGrid />
      <NavBar />
      <main className="relative z-10 max-w-6xl mx-auto px-6 py-10">
        <SectionHeader title="Mission Deck" subtitle="Active missions and campaign status" view={view} onView={setView} />
        {error && <ErrorBox msg={error} />}
        {view === "stats" && <MissionStats stats={missionStats} loading={loading} />}
        {view === "cards" && <IntelGrid docs={docs} />}
      </main>
    </div>
  );
}

function MissionStats({ stats, loading }: { stats: { total: number; drafts: number; ready: number; engaged: number } | null; loading: boolean }) {
  if (loading) return <Spinner />;
  if (!stats) return null;
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
      {[
        { label: "TOTAL", value: stats.total },
        { label: "DRAFTS", value: stats.drafts },
        { label: "READY", value: stats.ready },
        { label: "ENGAGED", value: stats.engaged },
      ].map((s) => (
        <StatCard key={s.label} label={s.label} value={s.value} />
      ))}
    </div>
  );
}

// ── Shared components ─────────────────────────────────────────────────────────

export function SectionHeader({ title, subtitle, view, onView }: {
  title: string; subtitle: string; view: View; onView: (v: View) => void;
}) {
  return (
    <div className="flex items-end justify-between mb-8">
      <div>
        <div className="font-mono text-xs text-amber-tac tracking-[0.4em] uppercase mb-1">Command Deck</div>
        <h1 className="font-mono text-xl font-semibold text-text-primary">{title}</h1>
        <p className="font-mono text-xs text-text-muted mt-1">{subtitle}</p>
      </div>
      <div className="flex items-center gap-0 border border-border-dim">
        {(["stats", "cards"] as View[]).map((v) => (
          <button key={v} onClick={() => onView(v)}
            className={`font-mono text-xs px-4 py-1.5 tracking-widest uppercase transition-colors ${
              view === v ? "bg-card text-amber-tac" : "text-text-muted hover:text-text-secondary"
            }`}>{v}</button>
        ))}
      </div>
    </div>
  );
}

export function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <div className="tac-border p-6 text-center bracket-corners">
      <div className="font-mono text-2xl font-bold text-amber-tac">{value}</div>
      <div className="font-mono text-xs text-text-muted tracking-widest mt-2">{label}</div>
    </div>
  );
}

export function IntelGrid({ docs }: { docs: IntelDocument[] }) {
  if (docs.length === 0) return (
    <div className="tac-border p-12 text-center bracket-corners">
      <p className="font-mono text-xs text-text-muted tracking-widest">NO DOCUMENTS</p>
    </div>
  );
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
      {docs.map((doc) => <IntelCard key={doc.uid} doc={doc} />)}
    </div>
  );
}

function IntelCard({ doc }: { doc: IntelDocument & { title?: string; tags?: string[] } }) {
  const { uid, source, source_url: sourceUrl } = doc;
  const title = (doc as { title?: string }).title || sourceUrl?.split("/").pop()?.replace(".md", "") || uid;
  const tags: string[] = (doc as { tags?: string[] }).tags ?? [];
  const isMission = tags.includes("topgun-mission");
  const isReady = tags.includes("topgun-mission-ready");

  const openSource = () => {
    if (source === "github" && sourceUrl) window.open(sourceUrl, "_blank");
    else if (source === "obsidian" && sourceUrl)
      window.open(`obsidian://open?path=${encodeURIComponent(sourceUrl)}`, "_blank");
  };

  return (
    <div className="tac-border flex flex-col aspect-square p-4 hover:bg-card transition-colors">
      <div className="flex items-center justify-between mb-3">
        <span className={`font-mono text-xs px-1.5 py-0.5 border tracking-widest ${
          source === "github" ? "border-green-live text-green-live" : "border-cyan-hud text-cyan-hud"
        }`}>{source === "github" ? "GH" : "OBS"}</span>
        <span className="font-mono text-xs text-text-muted/40">{uid.slice(0, 6)}</span>
      </div>
      <button onClick={openSource}
        className="flex-1 text-left font-mono text-xs text-text-primary leading-relaxed hover:text-amber-tac transition-colors line-clamp-4">
        {title}
      </button>
      <div className="mt-3">
        {isMission ? (
          <button className={`w-full font-mono text-xs py-1.5 tracking-widest border transition-colors ${
            isReady ? "border-green-live text-green-live hover:bg-green-live/10"
                    : "border-amber-tac text-amber-tac hover:bg-amber-tac/10"
          }`}>{isReady ? "→ ENGAGE" : "→ PLAN"}</button>
        ) : (
          <button onClick={openSource}
            className="w-full font-mono text-xs py-1.5 tracking-widest border border-border-dim text-text-muted hover:text-text-secondary transition-colors">
            → OPEN
          </button>
        )}
      </div>
    </div>
  );
}

function Spinner() {
  return <div className="flex items-center justify-center py-20">
    <span className="font-mono text-xs text-amber-tac animate-pulse_amber tracking-widest">COMPUTING...</span>
  </div>;
}

function ErrorBox({ msg }: { msg: string }) {
  return <div className="tac-border p-6 text-center mb-6">
    <p className="font-mono text-xs text-red-alert tracking-widest">ERROR</p>
    <p className="font-mono text-xs text-text-muted mt-1">{msg}</p>
  </div>;
}
