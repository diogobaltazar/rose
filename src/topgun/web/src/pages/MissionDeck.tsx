import { useState, useEffect, useCallback, useRef } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useToken } from "../hooks/useToken";
import NavBar from "../components/NavBar";
import HUDGrid from "../components/HUDGrid";
import { getIntelStats, getIntelList, peekCache, tagAsMission, invalidateCache } from "../api";
import { useEngagement } from "../context/EngagementContext";
import type { IntelStats, IntelDocument } from "../types";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { AttachAddon } from "@xterm/addon-attach";
import "@xterm/xterm/css/xterm.css";

const API_BASE = "/api";
const WS_BASE = `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/api`;

// ── Types ─────────────────────────────────────────────────────────────────────

type EnvPhase = "idle" | "creating" | "starting" | "running" | "stopped" | "failed";
type PanelSize = "half" | "full" | "bar";

interface GpEnvironment {
  id: string;
  phase: EnvPhase;
}

// ── Mission Deck page ─────────────────────────────────────────────────────────

export default function MissionDeck() {
  const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();
  const { getToken } = useToken();
  const [stats, setStats] = useState<IntelStats | null>(() => peekCache<IntelStats>("intel-stats"));
  const [docs, setDocs] = useState<IntelDocument[]>(() => peekCache<IntelDocument[]>("intel-list") ?? []);
  const [loading, setLoading] = useState<boolean>(() => peekCache("intel-stats") === null);
  const [error, setError] = useState<string | null>(null);

  const [env, setEnv] = useState<GpEnvironment | null>(null);
  const [panelSize, setPanelSize] = useState<PanelSize | null>(null);

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

  const pollPhase = useCallback(async (envId: string, token: string) => {
    const interval = setInterval(async () => {
      try {
        const resp = await fetch(`${API_BASE}/environments/${envId}`, {
          headers: { Authorization: `Bearer ${token}` },
        });
        const data = await resp.json();
        const phase: EnvPhase = data.phase ?? "starting";
        setEnv({ id: envId, phase });
        if (phase === "running" || phase === "failed") clearInterval(interval);
      } catch { /* keep polling */ }
    }, 4000);
    return interval;
  }, []);

  const handleCreateMission = useCallback(async () => {
    if (env && env.phase !== "idle" && env.phase !== "failed") return;
    setEnv({ id: "", phase: "creating" });
    try {
      const token = await getToken();
      const resp = await fetch(`${API_BASE}/environments`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
        body: JSON.stringify({ repo_url: "https://github.com/diogobaltazar/topgun" }),
      });
      if (!resp.ok) throw new Error(await resp.text());
      const data = await resp.json();
      const envId: string = data.id;
      const phase: EnvPhase = data.phase ?? "starting";
      setEnv({ id: envId, phase });
      if (phase !== "running") await pollPhase(envId, token);
    } catch (e) {
      setError(String(e));
      setEnv(null);
    }
  }, [env, getToken, pollPhase]);

  const handleOpenTerminal = () => {
    if (env?.phase === "running") setPanelSize("half");
  };

  if (isLoading || (!isAuthenticated && !error)) {
    return <div className="min-h-screen bg-base flex items-center justify-center">
      <span className="font-mono text-xs text-amber-tac animate-pulse_amber tracking-widest">LOADING...</span>
    </div>;
  }

  const { missions: engaged } = useEngagement();
  const missionDocs = docs.filter(d => d.labels?.includes("topgun-mission"));

  const btnPhase = env?.phase ?? "idle";
  const isStarting = btnPhase === "creating" || btnPhase === "starting";
  const isRunning = btnPhase === "running";

  return (
    <div className="min-h-screen bg-base text-text-primary">
      <HUDGrid />
      <NavBar />
      <main
        className="relative z-10 max-w-6xl mx-auto px-6 py-10"
        style={{ paddingBottom: panelSize === "bar" ? "3rem" : panelSize === "half" ? "50vh" : "2.5rem" }}
      >
        <div className="mb-8 flex items-end justify-between">
          <div>
            <div className="font-mono text-xs text-amber-tac tracking-[0.4em] uppercase mb-1">Command Deck</div>
            <h1 className="font-mono text-xl font-semibold text-text-primary">Mission Deck</h1>
            <p className="font-mono text-xs text-text-muted mt-1">Active missions and campaign status</p>
          </div>

          {/* Create Mission button */}
          <button
            onClick={isRunning ? handleOpenTerminal : handleCreateMission}
            disabled={isStarting}
            className={[
              "font-mono text-xs px-5 py-2 border tracking-widest transition-all shrink-0",
              isRunning
                ? "border-green-live text-green-live hover:bg-green-live/10 cursor-pointer"
                : isStarting
                ? "border-amber-tac text-amber-tac cursor-not-allowed animate-pulse_amber"
                : "border-border-dim text-text-muted hover:border-amber-tac hover:text-amber-tac",
            ].join(" ")}
            title={isRunning ? "Open Maverick terminal" : isStarting ? "Spinning up environment…" : "Create mission environment"}
          >
            {isRunning
              ? "● MAVERICK READY"
              : isStarting
              ? "○ SPINNING UP…"
              : "+ CREATE MISSION"}
          </button>
        </div>

        {error && <ErrorBox msg={error} />}
        <MissionPipeline stats={stats} engagedCount={engaged.length} loading={loading} />
        {!loading && (
          <div className="mt-8">
            {missionDocs.length === 0 ? (
              <div className="tac-border p-12 text-center bracket-corners">
                <p className="font-mono text-xs text-text-muted tracking-widest">NO TAGGED MISSIONS</p>
                <p className="font-mono text-xs text-text-muted/40 mt-2">Tag intel documents with topgun-mission to track them here</p>
              </div>
            ) : (
              <IntelGrid docs={missionDocs} onTagged={fetchAll} />
            )}
          </div>
        )}
      </main>

      {/* Maverick terminal panel */}
      {panelSize && env?.id && (
        <MaverickPanel
          envId={env.id}
          size={panelSize}
          onResize={setPanelSize}
          onClose={() => setPanelSize(null)}
          getToken={getToken}
        />
      )}
    </div>
  );
}

// ── Maverick terminal panel ───────────────────────────────────────────────────

function MaverickPanel({
  envId,
  size,
  onResize,
  onClose,
  getToken,
}: {
  envId: string;
  size: PanelSize;
  onResize: (s: PanelSize) => void;
  onClose: () => void;
  getToken: () => Promise<string>;
}) {
  const termRef = useRef<HTMLDivElement>(null);
  const termInstance = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!termRef.current || size === "bar") return;

    const term = new Terminal({
      fontFamily: '"JetBrains Mono", "Fira Code", monospace',
      fontSize: 13,
      theme: {
        background: "#080808",
        foreground: "#c8c8c8",
        cursor: "#f5a623",
        selectionBackground: "#f5a62333",
        black: "#1a1a1a", brightBlack: "#404040",
        red: "#ff4444", brightRed: "#ff6666",
        green: "#44d444", brightGreen: "#66ff66",
        yellow: "#f5a623", brightYellow: "#ffc04d",
        cyan: "#44cccc", brightCyan: "#66dddd",
      },
      cursorBlink: true,
      scrollback: 5000,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(termRef.current);
    fitAddon.fit();

    termInstance.current = term;

    const connect = async () => {
      try {
        const token = await getToken();
        const ws = new WebSocket(`${WS_BASE}/environments/${envId}/terminal?token=${encodeURIComponent(token)}`);
        ws.binaryType = "arraybuffer";
        wsRef.current = ws;
        const attachAddon = new AttachAddon(ws);
        term.loadAddon(attachAddon);
        ws.onclose = () => term.write("\r\n\x1b[33m[disconnected]\x1b[0m\r\n");
        ws.onerror = () => term.write("\r\n\x1b[31m[connection error]\x1b[0m\r\n");
      } catch {
        term.write("\r\n\x1b[31m[failed to connect]\x1b[0m\r\n");
      }
    };

    connect();

    const handleResize = () => fitAddon.fit();
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      wsRef.current?.close();
      term.dispose();
      termInstance.current = null;
    };
  }, [envId, size, getToken]);

  // Refit on size change
  useEffect(() => {
    if (termInstance.current && size !== "bar") {
      setTimeout(() => {
        try { new FitAddon().fit(); } catch { /* ignore */ }
      }, 100);
    }
  }, [size]);

  const NAVBAR_H = 45;

  const panelStyle: React.CSSProperties =
    size === "full"
      ? { top: NAVBAR_H, bottom: 0, left: 0, right: 0, height: `calc(100vh - ${NAVBAR_H}px)` }
      : size === "half"
      ? { bottom: 0, left: 0, right: 0, height: "50vh" }
      : { bottom: 0, left: 0, right: 0, height: "2.5rem" };

  return (
    <div
      className="fixed z-50 bg-[#080808] border-t border-border-dim flex flex-col"
      style={panelStyle}
    >
      {/* Header bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-border-dim shrink-0 h-10">
        <div className="flex items-center gap-3">
          <span className="w-2 h-2 rounded-full bg-green-live shrink-0" />
          <span className="font-mono text-xs text-amber-tac tracking-widest">MAVERICK</span>
          <span className="font-mono text-xs text-text-muted/50">{envId.slice(0, 8)}</span>
        </div>
        <div className="flex items-center gap-2">
          {size === "bar" && (
            <button
              onClick={() => onResize("half")}
              className="font-mono text-xs text-text-muted hover:text-amber-tac px-2 py-0.5"
              title="Expand"
            >▲</button>
          )}
          {size === "half" && (
            <>
              <button
                onClick={() => onResize("full")}
                className="font-mono text-xs text-text-muted hover:text-amber-tac px-2 py-0.5"
                title="Full screen"
              >⤢</button>
              <button
                onClick={() => onResize("bar")}
                className="font-mono text-xs text-text-muted hover:text-amber-tac px-2 py-0.5"
                title="Minimise"
              >▼</button>
            </>
          )}
          {size === "full" && (
            <button
              onClick={() => onResize("half")}
              className="font-mono text-xs text-text-muted hover:text-amber-tac px-2 py-0.5"
              title="Restore"
            >⤡</button>
          )}
          <button
            onClick={onClose}
            className="font-mono text-xs text-text-muted hover:text-red-alert px-2 py-0.5"
            title="Close"
          >✕</button>
        </div>
      </div>

      {/* Terminal area */}
      {size !== "bar" && (
        <div ref={termRef} className="flex-1 overflow-hidden p-1" />
      )}
    </div>
  );
}

// ── Pipeline ──────────────────────────────────────────────────────────────────

function MissionPipeline({
  stats,
  engagedCount,
  loading,
}: {
  stats: IntelStats | null;
  engagedCount: number;
  loading: boolean;
}) {
  if (loading) return <Spinner />;
  if (!stats) return null;

  const intel = stats.total;
  const missions = stats.missions;
  const engaged = engagedCount;
  const backlog = intel - missions;

  const missionPct = intel > 0 ? Math.round((missions / intel) * 100) : 0;
  const engagePct = missions > 0 ? Math.round((engaged / missions) * 100) : 0;

  const stages = [
    { label: "INTEL", sub: "sources indexed", value: intel, pct: null as number | null, color: "text-text-secondary", bar: "bg-text-muted/40" },
    { label: "MISSIONS", sub: "tagged for ops", value: missions, pct: missionPct, color: "text-amber-tac", bar: "bg-amber-tac" },
    { label: "ENGAGED", sub: "active sorties", value: engaged, pct: engagePct, color: "text-green-live", bar: "bg-green-live" },
  ];
  const maxVal = Math.max(intel, 1);

  return (
    <div className="tac-border p-5 animate-fadeIn">
      <div className="flex items-center justify-between mb-5">
        <div className="font-mono text-xs text-text-muted tracking-widest uppercase">Ops Pipeline</div>
        {backlog > 0 && (
          <div className="font-mono text-xs text-text-muted/50">
            {backlog} source{backlog !== 1 ? "s" : ""} untagged
          </div>
        )}
      </div>

      <div className="flex items-end gap-3">
        {stages.map((s, i) => (
          <div key={s.label} className="contents">
            {i > 0 && (
              <div className="flex-none self-center pb-8 font-mono text-xs text-border-dim">──►</div>
            )}
            <div className="flex-1 min-w-0">
              <div className={`font-mono text-3xl font-bold tabular-nums ${s.color}`}>{s.value}</div>
              {s.pct !== null && (
                <div className="font-mono text-xs text-text-muted/60 tabular-nums mt-0.5">
                  {s.pct}%
                </div>
              )}
              <div className={`font-mono text-xs tracking-widest uppercase mt-2 ${s.color}`}>{s.label}</div>
              <div className="font-mono text-[10px] text-text-muted/50 mt-0.5">{s.sub}</div>
              <div className="h-px bg-border-dim mt-3">
                <div
                  className={`h-px ${s.bar} transition-all duration-700`}
                  style={{ width: `${(s.value / maxVal) * 100}%` }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>
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

export function IntelGrid({
  docs,
  onTagged,
  selectedUids,
  onToggle,
}: {
  docs: IntelDocument[];
  onTagged?: () => void;
  selectedUids?: Set<string>;
  onToggle?: (uid: string) => void;
}) {
  if (docs.length === 0) return (
    <div className="tac-border p-12 text-center bracket-corners">
      <p className="font-mono text-xs text-text-muted tracking-widest">NO DOCUMENTS</p>
    </div>
  );
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
      {docs.map((doc, i) => (
        <IntelCard
          key={doc.uid}
          doc={doc}
          index={i}
          onTagged={onTagged}
          selected={selectedUids?.has(doc.uid) ?? false}
          onToggle={onToggle}
        />
      ))}
    </div>
  );
}

function IntelCard({
  doc,
  index = 0,
  onTagged,
  selected = false,
  onToggle,
}: {
  doc: IntelDocument;
  index?: number;
  onTagged?: () => void;
  selected?: boolean;
  onToggle?: (uid: string) => void;
}) {
  const { uid, source, source_url: sourceUrl } = doc;
  const title = doc.title || sourceUrl?.split("/").pop()?.replace(".md", "") || uid;
  const labels = doc.labels ?? [];

  const { engage, abort, isEngaged } = useEngagement();
  const { getToken } = useToken();
  const engaged = isEngaged(uid);
  const isMission = labels.includes("topgun-mission");
  const [tagging, setTagging] = useState(false);
  const [tagError, setTagError] = useState<string | null>(null);

  const openSource = () => {
    if (source === "github" && sourceUrl) {
      window.open(sourceUrl, "_blank");
    } else if (source === "obsidian" && sourceUrl) {
      const parts = sourceUrl.replace(/^vault\//, "").split("/");
      const file = parts.join("/").replace(/\.md$/, "");
      window.open(`obsidian://open?vault=vault&file=${encodeURIComponent(file)}`, "_blank");
    }
  };

  const handleTag = async () => {
    if (!sourceUrl || source !== "github" || tagging) return;
    setTagging(true);
    setTagError(null);
    try {
      await tagAsMission(await getToken(), uid, sourceUrl);
      invalidateCache("intel-list", "intel-stats");
      onTagged?.();
    } catch (e) {
      setTagError(String(e));
    } finally {
      setTagging(false);
    }
  };

  const handleEngage = () => engaged ? abort(uid) : engage(uid, title);

  return (
    <div
      className="tac-border flex flex-col p-4 hover:bg-card transition-colors animate-fadeIn"
      style={{ animationDelay: `${index * 0.04}s` }}
    >
      {/* Top row */}
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          {onToggle && (
            <button
              onClick={e => { e.stopPropagation(); onToggle(uid); }}
              title={selected ? "Remove from KB context" : "Add to KB context"}
              className={`w-4 h-4 border flex items-center justify-center shrink-0 transition-colors ${
                selected
                  ? "border-amber-tac bg-amber-tac/20 text-amber-tac"
                  : "border-border-dim text-transparent hover:border-text-muted"
              }`}
            >
              <span className="text-[8px] leading-none">{selected ? "✓" : ""}</span>
            </button>
          )}
          <span className={`font-mono text-xs px-1.5 py-0.5 border tracking-widest ${
            source === "github" ? "border-green-live text-green-live" : "border-cyan-hud text-cyan-hud"
          }`}>{source === "github" ? "GH" : "OBS"}</span>
        </div>
        <span className="font-mono text-xs text-text-muted/40">{uid.slice(0, 6)}</span>
      </div>

      {/* Title */}
      <button
        onClick={openSource}
        className="flex-1 text-left font-mono text-xs text-text-primary leading-relaxed hover:text-amber-tac transition-colors line-clamp-4 min-h-[3.5rem]"
      >
        {title}
      </button>

      {/* Action */}
      <div className="mt-3 space-y-1.5">
        {tagError && <p className="font-mono text-[10px] text-red-alert">{tagError}</p>}
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
          <div className="flex gap-1.5">
            <button
              onClick={openSource}
              className="flex-1 font-mono text-xs py-1.5 tracking-widest border border-border-dim text-text-muted hover:text-text-secondary transition-colors"
            >
              → OPEN
            </button>
            {source === "github" && (
              <button
                onClick={handleTag}
                disabled={tagging}
                title="Tag as mission"
                className="font-mono text-xs px-2 py-1.5 border border-border-dim text-text-muted/50 hover:border-amber-tac hover:text-amber-tac transition-colors disabled:opacity-30"
              >
                {tagging ? "…" : "⊕"}
              </button>
            )}
          </div>
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
