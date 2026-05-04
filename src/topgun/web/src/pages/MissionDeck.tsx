import { useState, useEffect, useCallback } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useToken } from "../hooks/useToken";
import NavBar from "../components/NavBar";
import HUDGrid from "../components/HUDGrid";
import { getIntelStats, getIntelList, peekCache } from "../api";
import type { IntelStats, IntelDocument } from "../types";

export default function MissionDeck() {
  const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();
  const { getToken } = useToken();
  const [stats, setStats] = useState<IntelStats | null>(() => peekCache<IntelStats>("intel-stats"));
  const [docs, setDocs] = useState<IntelDocument[]>(() => peekCache<IntelDocument[]>("intel-list") ?? []);
  const [loading, setLoading] = useState<boolean>(() => peekCache("intel-stats") === null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) loginWithRedirect();
  }, [isAuthenticated, isLoading, loginWithRedirect]);

  const fetchAll = useCallback(async () => {
    try {
      const token = await getToken();
      const [s, d] = await Promise.all([getIntelStats(token), getIntelList(token)]);
      setStats(s);
      setDocs(d);
    } catch (e) { setError(String(e)); }
    finally { setLoading(false); }
  }, [getToken]);

  useEffect(() => { if (isAuthenticated) fetchAll(); }, [isAuthenticated, fetchAll]);

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
        <div className="mb-8">
          <div className="font-mono text-xs text-amber-tac tracking-[0.4em] uppercase mb-1">Command Deck</div>
          <h1 className="font-mono text-xl font-semibold text-text-primary">Mission Deck</h1>
          <p className="font-mono text-xs text-text-muted mt-1">Active missions and campaign status</p>
        </div>
        {error && <ErrorBox msg={error} />}
        <MissionStats stats={missionStats} loading={loading} />
        {!loading && <div className="mt-8"><IntelGrid docs={docs} /></div>}
      </main>
    </div>
  );
}

function MissionStats({ stats, loading }: { stats: { total: number; drafts: number; ready: number; engaged: number } | null; loading: boolean }) {
  if (loading) return <Spinner />;
  if (!stats) return null;
  const items = [
    { label: "TOTAL", value: stats.total },
    { label: "DRAFTS", value: stats.drafts },
    { label: "READY", value: stats.ready },
    { label: "ENGAGED", value: stats.engaged },
  ];
  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
      {items.map((s, i) => <StatCard key={s.label} label={s.label} value={s.value} index={i} />)}
    </div>
  );
}

// ── Shared components ─────────────────────────────────────────────────────────


export function StatCard({ label, value, index = 0 }: { label: string; value: number; index?: number }) {
  return (
    <div
      className="tac-border p-6 text-center bracket-corners animate-fadeIn"
      style={{ animationDelay: `${index * 0.07}s` }}
    >
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
      {docs.map((doc, i) => <IntelCard key={doc.uid} doc={doc} index={i} />)}
    </div>
  );
}

function IntelCard({ doc, index = 0 }: { doc: IntelDocument & { title?: string; tags?: string[] }; index?: number }) {
  const { uid, source, source_url: sourceUrl } = doc;
  const title = (doc as { title?: string }).title || sourceUrl?.split("/").pop()?.replace(".md", "") || uid;
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
    <div
      className="tac-border flex flex-col aspect-square p-4 hover:bg-card transition-colors animate-fadeIn"
      style={{ animationDelay: `${index * 0.04}s` }}
    >
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

export function Spinner() {
  return (
    <div className="flex items-center justify-center gap-2 py-20">
      {[0, 1, 2].map(i => (
        <div
          key={i}
          className="w-1.5 h-1.5 rounded-full bg-amber-tac animate-pulse_amber"
          style={{ animationDelay: `${i * 0.25}s` }}
        />
      ))}
    </div>
  );
}

function ErrorBox({ msg }: { msg: string }) {
  return <div className="tac-border p-6 text-center mb-6">
    <p className="font-mono text-xs text-red-alert tracking-widest">ERROR</p>
    <p className="font-mono text-xs text-text-muted mt-1">{msg}</p>
  </div>;
}
