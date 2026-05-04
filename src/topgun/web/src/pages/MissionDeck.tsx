import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useToken } from "../hooks/useToken";
import NavBar from "../components/NavBar";
import HUDGrid from "../components/HUDGrid";
import { getIntelStats, getIntelList, peekCache, tagAsMission, invalidateCache } from "../api";
import { useEngagement } from "../context/EngagementContext";
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

function makeTermLines(uid: string, title: string): string[] {
  return [
    `$ /topgun-mission-plan intel document ${uid}`,
    "",
    "◆  Spawning ONA environment...",
    "◆  Loading Claude Code agent...",
    "◆  Loading mission planner skill...",
    "",
    `◆  Reading intel: "${title}"`,
    "◆  Fetching repository context...",
    "◆  Scanning codebase structure...",
    "◆  Mapping affected components...",
    "◆  Estimating scope and complexity...",
    "",
    "  ┌─────────────────────────────────────┐",
    "  │  MISSION PLAN DRAFT                 │",
    "  ├─────────────────────────────────────┤",
    "  │  Priority    HIGH                   │",
    "  │  Complexity  MEDIUM                 │",
    "  │  Est tokens  ~240k                  │",
    "  │  Est cost    ~$2.40                 │",
    "  │  Crew        2 pilots               │",
    "  └─────────────────────────────────────┘",
    "",
    "◆  Plan ready. COMMIT to engage · ABORT to cancel.",
  ];
}

function IntelCard({ doc, index = 0 }: { doc: IntelDocument; index?: number }) {
  const { uid, source, source_url: sourceUrl } = doc;
  const title = doc.title || sourceUrl?.split("/").pop()?.replace(".md", "") || uid;
  const labels = doc.labels ?? [];
  const isMission = labels.includes("topgun-mission");

  const { engage, abort, isEngaged } = useEngagement();
  const { getToken } = useToken();
  const engaged = isEngaged(uid);

  type OnaState = "idle" | "warming" | "ready";
  const [onaState, setOnaState] = useState<OnaState>("idle");
  const [panelOpen, setPanelOpen] = useState(false);
  const [termLines, setTermLines] = useState<string[]>([]);
  const [committing, setCommitting] = useState(false);
  const [commitDone, setCommitDone] = useState(false);
  const [commitError, setCommitError] = useState<string | null>(null);
  const termRef = useRef<HTMLDivElement>(null);

  const openSource = () => {
    if (source === "github" && sourceUrl) {
      window.open(sourceUrl, "_blank");
    } else if (source === "obsidian" && sourceUrl) {
      const parts = sourceUrl.replace(/^vault\//, "").split("/");
      const file = parts.join("/").replace(/\.md$/, "");
      window.open(`obsidian://open?vault=vault&file=${encodeURIComponent(file)}`, "_blank");
    }
  };

  const startStream = (uid: string, title: string) => {
    const lines = makeTermLines(uid, title);
    lines.forEach((line, i) => {
      setTimeout(() => {
        setTermLines(prev => [...prev, line]);
        if (termRef.current) termRef.current.scrollTop = termRef.current.scrollHeight;
      }, i * 140);
    });
  };

  const handleOnaClick = () => {
    if (onaState === "idle") {
      setOnaState("warming");
      setTimeout(() => setOnaState("ready"), 5000);
    } else if (onaState === "ready") {
      const opening = !panelOpen;
      setPanelOpen(opening);
      if (opening && termLines.length === 0) startStream(uid, title);
    }
  };

  const handleCommit = async () => {
    if (!sourceUrl || source !== "github") return;
    setCommitting(true);
    setCommitError(null);
    try {
      await tagAsMission(await getToken(), uid, sourceUrl);
      setCommitDone(true);
      setTermLines(prev => [...prev, "", "◆  Tagged as MISSION. Panel closing..."]);
      setTimeout(() => { setPanelOpen(false); invalidateCache("intel-list", "intel-stats"); }, 1200);
    } catch (e) {
      setCommitError(String(e));
      setTermLines(prev => [...prev, `✗  Error: ${String(e)}`]);
    } finally {
      setCommitting(false);
    }
  };

  const handleEngage = () => engaged ? abort(uid) : engage(uid, title);

  return (
    <>
      <div
        className="tac-border flex flex-col p-4 hover:bg-card transition-colors animate-fadeIn"
        style={{ animationDelay: `${index * 0.04}s` }}
      >
        {/* Top row */}
        <div className="flex items-center justify-between mb-3">
          <span className={`font-mono text-xs px-1.5 py-0.5 border tracking-widest ${
            source === "github" ? "border-green-live text-green-live" : "border-cyan-hud text-cyan-hud"
          }`}>{source === "github" ? "GH" : "OBS"}</span>

          <div className="flex items-center gap-2">
            {onaState === "warming" && (
              <div className="w-1.5 h-1.5 rounded-full bg-amber-tac animate-pulse_amber shrink-0" title="ONA warming up..." />
            )}
            {onaState === "ready" && (
              <div className={`w-1.5 h-1.5 rounded-full shrink-0 ${panelOpen ? "bg-amber-tac" : "bg-green-live"}`} />
            )}
            <button
              onClick={handleOnaClick}
              disabled={onaState === "warming"}
              title={onaState === "idle" ? "Start ONA planning" : "Toggle mission planning panel"}
              className={`font-mono text-xs border px-1.5 py-0.5 leading-none transition-colors ${
                onaState === "warming"
                  ? "border-border-dim text-text-muted/30 cursor-not-allowed"
                  : panelOpen
                  ? "border-amber-tac text-amber-tac"
                  : "border-border-dim text-text-muted hover:border-amber-tac hover:text-amber-tac"
              }`}
            >
              ⊕
            </button>
            <span className="font-mono text-xs text-text-muted/40">{uid.slice(0, 6)}</span>
          </div>
        </div>

        {/* Title */}
        <button
          onClick={openSource}
          className="flex-1 text-left font-mono text-xs text-text-primary leading-relaxed hover:text-amber-tac transition-colors line-clamp-4 min-h-[3.5rem]"
        >
          {title}
        </button>

        {/* Action */}
        <div className="mt-3">
          {isMission ? (
            <button
              onClick={handleEngage}
              className={`w-full font-mono text-xs py-1.5 tracking-widest border transition-colors ${
                engaged
                  ? "border-red-alert text-red-alert hover:bg-red-alert/10"
                  : "border-green-live text-green-live hover:bg-green-live/10"
              }`}
            >
              {engaged ? "✕ ABORT" : "→ ENGAGE"}
            </button>
          ) : (
            <button
              onClick={openSource}
              className="w-full font-mono text-xs py-1.5 tracking-widest border border-border-dim text-text-muted hover:text-text-secondary transition-colors"
            >
              → OPEN
            </button>
          )}
        </div>
      </div>

      {/* ONA panel */}
      {panelOpen && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setPanelOpen(false)} />
          <div className="fixed top-0 right-0 h-screen w-1/2 z-50 bg-[#080808] border-l border-border-dim flex flex-col">
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-3 border-b border-border-dim shrink-0">
              <div>
                <div className="font-mono text-xs text-amber-tac tracking-widest">ONA ENVIRONMENT</div>
                <div className="font-mono text-xs text-text-muted mt-0.5 truncate">{title}</div>
              </div>
              <button onClick={() => setPanelOpen(false)} className="font-mono text-xs text-text-muted hover:text-amber-tac ml-4 shrink-0">✕</button>
            </div>

            {/* Terminal */}
            <div ref={termRef} className="flex-1 overflow-y-auto p-5 space-y-0.5">
              {termLines.map((line, i) => (
                <div key={i} className={
                  line.startsWith("$") ? "font-mono text-xs text-amber-tac" :
                  line.startsWith("◆") ? "font-mono text-xs text-green-live" :
                  line.startsWith("  ┌") || line.startsWith("  │") || line.startsWith("  ├") || line.startsWith("  └")
                    ? "font-mono text-xs text-cyan-hud" :
                  line.startsWith("✗") ? "font-mono text-xs text-red-alert" :
                  line === "" ? "h-2 block" :
                  "font-mono text-xs text-text-secondary"
                }>
                  {line || "\u00a0"}
                </div>
              ))}
              {termLines.length > 0 && termLines.length < makeTermLines(uid, title).length && (
                <span className="font-mono text-xs text-amber-tac animate-blink">█</span>
              )}
            </div>

            {/* Actions */}
            {!commitDone && source === "github" && (
              <div className="flex gap-2 px-5 py-4 border-t border-border-dim shrink-0">
                <button
                  onClick={handleCommit}
                  disabled={committing}
                  className="font-mono text-xs px-4 py-1.5 border border-green-live text-green-live hover:bg-green-live/10 tracking-widest disabled:opacity-40"
                >
                  {committing ? "COMMITTING..." : "COMMIT"}
                </button>
                <button
                  onClick={() => setPanelOpen(false)}
                  className="font-mono text-xs px-4 py-1.5 border border-red-alert text-red-alert hover:bg-red-alert/10 tracking-widest"
                >
                  ABORT
                </button>
                {commitError && <span className="font-mono text-xs text-red-alert self-center ml-2">{commitError}</span>}
              </div>
            )}
          </div>
        </>
      )}
    </>
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
