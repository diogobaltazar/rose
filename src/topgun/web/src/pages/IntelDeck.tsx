import { useState, useEffect, useCallback, useRef } from "react";
import { Link } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { useToken } from "../hooks/useToken";
import NavBar from "../components/NavBar";
import HUDGrid from "../components/HUDGrid";
import {
  getIntelStats, getIntelList, searchIntel, peekCache,
  askAssistant, createMissionPlan, getConnections,
} from "../api";
import { renderMarkdown } from "../utils/markdown";
import type { ChatMessage } from "../api";
import type { MissionPlanResult } from "../api";
import { Spinner, IntelGrid } from "./MissionDeck";
import type { IntelStats, IntelDocument, IntelSearchResult } from "../types";

// ── Loading overlay ───────────────────────────────────────────────────────────

function FetchingIntel() {
  return (
    <div className="fixed inset-0 z-50 flex flex-col items-center justify-center bg-base/90 backdrop-blur-sm">
      <div className="flex gap-2 mb-4">
        {[0, 1, 2].map(i => (
          <div
            key={i}
            className="w-2 h-2 rounded-full bg-amber-tac animate-pulse_amber"
            style={{ animationDelay: `${i * 0.25}s` }}
          />
        ))}
      </div>
      <div className="font-mono text-xs text-amber-tac tracking-[0.3em] uppercase animate-pulse_amber">
        Fetching intel
      </div>
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export default function IntelDeck() {
  const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();
  const { getToken } = useToken();

  const [stats, setStats] = useState<IntelStats | null>(() => peekCache<IntelStats>("intel-stats"));
  const [docs, setDocs] = useState<IntelDocument[]>(() => peekCache<IntelDocument[]>("intel-list") ?? []);
  const [loading, setLoading] = useState<boolean>(() => peekCache("intel-stats") === null);
  const [llmConnected, setLlmConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Selection state lives here so KB and Sources stay in sync
  const [selectedUids, setSelectedUids] = useState<Set<string>>(new Set());

  useEffect(() => {
    if (!isLoading && !isAuthenticated) loginWithRedirect();
  }, [isAuthenticated, isLoading, loginWithRedirect]);

  const fetchAll = useCallback(async () => {
    try {
      const token = await getToken();
      const [s, d, conn] = await Promise.all([
        getIntelStats(token),
        getIntelList(token),
        getConnections(token).catch(() => null),
      ]);
      setStats(s);
      setDocs(d);
      setLlmConnected(conn?.llm?.working ?? false);
    } catch (e) { setError(String(e)); }
    finally { setLoading(false); }
  }, [getToken]);

  useEffect(() => { if (isAuthenticated) fetchAll(); }, [isAuthenticated, fetchAll]);

  const toggleDoc = (uid: string) =>
    setSelectedUids(prev => {
      const next = new Set(prev);
      next.has(uid) ? next.delete(uid) : next.add(uid);
      return next;
    });

  const selectedDocs = docs.filter(d => selectedUids.has(d.uid));

  if (isLoading || (!isAuthenticated && !error)) {
    return <div className="min-h-screen bg-base"><FetchingIntel /></div>;
  }

  return (
    <div className="min-h-screen bg-base text-text-primary">
      {loading && <FetchingIntel />}
      <HUDGrid />
      <NavBar />
      <main className="relative z-10 max-w-6xl mx-auto px-6 py-10 space-y-14">

        {/* Header + Stats */}
        <div>
          <div className="font-mono text-xs text-amber-tac tracking-[0.4em] uppercase mb-1">Command Deck</div>
          <h1 className="font-mono text-xl font-semibold text-text-primary">Intel</h1>
          {error && (
            <div className="mt-3 tac-border p-4">
              <p className="font-mono text-xs text-red-alert tracking-widest">{error}</p>
            </div>
          )}
          {stats && !loading && <IntelSignalBoard stats={stats} />}
        </div>

        {/* ── KNOWLEDGE BASE ──────────────────────────────────────────────── */}
        <KnowledgeBaseSection
          selectedDocs={selectedDocs}
          llmConnected={llmConnected}
          onMissionCreated={fetchAll}
        />

        {/* ── INTEL SOURCES ───────────────────────────────────────────────── */}
        <IntelSourcesSection
          docs={docs}
          loading={loading}
          selectedUids={selectedUids}
          onToggle={toggleDoc}
          onTagged={fetchAll}
        />

        {/* ── DOCS ────────────────────────────────────────────────────────── */}
        <DocsSection />

      </main>
    </div>
  );
}

// ── Knowledge Base section ────────────────────────────────────────────────────

function buildSystemPrompt(selected: IntelDocument[]): string {
  const base =
    "You are an AI assistant for ALMA VICTORIA TOPGUN — an autonomous software development platform. " +
    "Help the user analyse their intel knowledge base. Be concise and precise.";
  if (selected.length === 0) return base;

  const ctx = selected.map(d => {
    const title = d.title ?? d.source_url.split("/").pop() ?? d.uid;
    if (d.source === "github") {
      return `- GitHub issue: "${title}" — ${d.source_url}${d.labels?.length ? ` [labels: ${d.labels.join(", ")}]` : ""}`;
    }
    return `- Document: "${title}" — ${d.source_url}`;
  }).join("\n");

  return (
    base +
    "\n\nThe user has selected the following intel sources as context:\n" +
    ctx +
    "\n\nFor GitHub issues, reference the issue title and URL in your responses. " +
    "If asked to help create a mission or break down work, produce a clear, structured mission plan " +
    "the user can convert into GitHub issues."
  );
}

function KnowledgeBaseSection({
  selectedDocs,
  llmConnected,
  onMissionCreated,
}: {
  selectedDocs: IntelDocument[];
  llmConnected: boolean;
  onMissionCreated: () => void;
}) {
  const { getToken } = useToken();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [chatLoading, setChatLoading] = useState(false);
  const [chatError, setChatError] = useState<string | null>(null);
  const [missionOpen, setMissionOpen] = useState(false);
  const chatBottomRef = useRef<HTMLDivElement>(null);

  const chatOpen = messages.length > 0;

  const send = async (text: string) => {
    if (!text.trim() || chatLoading || !llmConnected) return;
    const next: ChatMessage[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    setInput("");
    setChatLoading(true);
    setChatError(null);
    try {
      const token = await getToken();
      const system = buildSystemPrompt(selectedDocs);
      const response = await askAssistant(token, next, system);
      setMessages([...next, { role: "assistant", content: response }]);
    } catch (e) {
      setChatError(String(e));
    } finally {
      setChatLoading(false);
    }
  };

  useEffect(() => {
    chatBottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, chatLoading]);

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); }
  };

  return (
    <section>
      <SectionHeader
        label="KNOWLEDGE BASE"
        description="Select sources below, ask questions, convert insights into missions."
      />

      {!llmConnected ? (
        <div className="tac-border p-6 flex items-center justify-between">
          <div>
            <div className="font-mono text-xs text-text-primary">AI PROVIDER NOT CONFIGURED</div>
            <div className="font-mono text-xs text-text-muted mt-1">
              Add an API key in Settings to enable the knowledge base chat.
            </div>
          </div>
          <Link
            to="/deck/settings"
            className="font-mono text-xs px-4 py-1.5 border border-amber-tac/40 text-amber-tac/60 hover:border-amber-tac hover:text-amber-tac tracking-widest shrink-0"
          >
            SETTINGS →
          </Link>
        </div>
      ) : (
        <>
          {/* Selected context summary */}
          {selectedDocs.length > 0 && (
            <div className="mb-3 flex flex-wrap gap-2 items-center">
              <span className="font-mono text-xs text-text-muted/60 tracking-wide">
                Context:
              </span>
              {selectedDocs.map(d => {
                const title = d.title ?? d.source_url.split("/").pop() ?? d.uid;
                return (
                  <span
                    key={d.uid}
                    className="font-mono text-xs px-2 py-0.5 border border-amber-tac/40 text-amber-tac/80 max-w-[200px] truncate"
                    title={title}
                  >
                    {d.source === "github" ? "⊙ " : "◈ "}
                    {title.length > 24 ? title.slice(0, 22) + "…" : title}
                  </span>
                );
              })}
            </div>
          )}

          {/* Chat window */}
          {chatOpen && (
            <div className="tac-border mb-4">
              <div className="flex items-center justify-between px-4 py-2.5 border-b border-border-dim">
                <div className="font-mono text-xs text-amber-tac tracking-[0.3em] uppercase">Intel Chat</div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setMissionOpen(true)}
                    className="font-mono text-xs px-3 py-1 border border-amber-tac/60 text-amber-tac/80 hover:border-amber-tac hover:text-amber-tac tracking-widest"
                  >
                    CONVERT INTO MISSION
                  </button>
                  <button
                    onClick={() => { setMessages([]); setChatError(null); }}
                    className="font-mono text-xs text-text-muted hover:text-red-alert px-2 tracking-widest"
                  >
                    ✕
                  </button>
                </div>
              </div>
              <div className="px-4 py-4 space-y-4 max-h-96 overflow-y-auto">
                {messages.map((m, i) => (
                  <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
                    {m.role === "user" ? (
                      <div className="max-w-[80%] bg-amber-tac/10 border border-amber-tac/30 px-4 py-2">
                        <p className="font-mono text-xs text-amber-tac whitespace-pre-wrap">{m.content}</p>
                      </div>
                    ) : (
                      <div className="max-w-[95%]">
                        <div className="font-mono text-xs text-text-muted tracking-widest mb-1">TOPGUN AI</div>
                        <div className="space-y-0.5">
                          {renderMarkdown(m.content)}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
                {chatLoading && (
                  <div className="font-mono text-xs text-amber-tac animate-pulse_amber tracking-widest">THINKING…</div>
                )}
                {chatError && (
                  <div className="font-mono text-xs text-red-alert border border-red-alert/30 px-3 py-2">{chatError}</div>
                )}
                <div ref={chatBottomRef} />
              </div>
            </div>
          )}

          {/* Input */}
          <div className="tac-border">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder={
                chatOpen
                  ? "Ask a follow-up… (Enter to send, Shift+Enter for newline)"
                  : selectedDocs.length > 0
                  ? `Ask about ${selectedDocs.length} selected source${selectedDocs.length !== 1 ? "s" : ""}…`
                  : "Select sources below, then ask anything about your intel…"
              }
              rows={chatOpen ? 3 : 5}
              className="w-full bg-transparent px-4 py-4 font-mono text-sm text-text-primary placeholder:text-text-muted focus:outline-none resize-none leading-relaxed"
            />
            <div className="flex items-center justify-between px-4 py-2.5 border-t border-border-dim">
              <div className="font-mono text-xs text-text-muted/50">
                {selectedDocs.length > 0
                  ? `${selectedDocs.length} source${selectedDocs.length !== 1 ? "s" : ""} in context`
                  : "No sources selected — check boxes below"}
              </div>
              <button
                onClick={() => send(input)}
                disabled={!input.trim() || chatLoading}
                className="font-mono text-xs px-5 py-1.5 border border-amber-tac text-amber-tac hover:bg-amber-tac/10 tracking-widest disabled:opacity-40"
              >
                SEND
              </button>
            </div>
          </div>
        </>
      )}

      {missionOpen && (
        <MissionModal
          messages={messages}
          selectedDocs={selectedDocs}
          onClose={() => setMissionOpen(false)}
          onCreated={() => { setMissionOpen(false); onMissionCreated(); }}
        />
      )}
    </section>
  );
}

// ── Mission creation modal ────────────────────────────────────────────────────

function MissionModal({
  messages,
  selectedDocs,
  onClose,
  onCreated,
}: {
  messages: ChatMessage[];
  selectedDocs: IntelDocument[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const { getToken } = useToken();
  const [title, setTitle] = useState("");
  const [creating, setCreating] = useState(false);
  const [result, setResult] = useState<MissionPlanResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const missionBody = messages
    .map(m => (m.role === "user" ? `> ${m.content}` : m.content))
    .join("\n\n");

  const sourceUrls = selectedDocs.filter(d => d.source_url).map(d => d.source_url);

  const deploy = async () => {
    if (!title.trim() || creating) return;
    setCreating(true);
    setError(null);
    try {
      const token = await getToken();
      const res = await createMissionPlan(token, title.trim(), missionBody, sourceUrls);
      setResult(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="w-full max-w-lg bg-base border border-border-dim">
        <div className="flex items-center justify-between px-5 py-3 border-b border-border-dim">
          <div className="font-mono text-xs text-amber-tac tracking-[0.3em] uppercase">Convert Into Mission</div>
          <button onClick={onClose} className="font-mono text-xs text-text-muted hover:text-red-alert tracking-widest px-2">✕</button>
        </div>

        {result ? (
          <div className="px-5 py-6 space-y-4">
            <div className="font-mono text-xs text-green-live tracking-widest">MISSION DEPLOYED</div>
            <div className="space-y-2">
              {result.github_issues.map(issue => (
                <a key={issue.url} href={issue.url} target="_blank" rel="noopener noreferrer"
                  className="block tac-border p-3 hover:border-amber-tac/60 transition-colors">
                  <div className="font-mono text-xs text-text-muted tracking-widest">{issue.repo}</div>
                  <div className="font-mono text-xs text-amber-tac mt-0.5">Issue #{issue.number} →</div>
                </a>
              ))}
            </div>
            <div className="font-mono text-xs text-text-muted/60 leading-relaxed">
              Vault file: {result.vault_file} — saved to Drive.<br />
              Issues tagged <span className="text-amber-tac">topgun-mission</span> and will appear in Intel Sources.
            </div>
            <button onClick={onCreated}
              className="font-mono text-xs px-5 py-2 border border-amber-tac text-amber-tac hover:bg-amber-tac/10 tracking-widest">
              DONE
            </button>
          </div>
        ) : (
          <div className="px-5 py-6 space-y-5">
            <div>
              <label className="font-mono text-xs text-text-muted tracking-widest block mb-2">MISSION TITLE</label>
              <input type="text" value={title} onChange={e => setTitle(e.target.value)}
                onKeyDown={e => e.key === "Enter" && deploy()}
                placeholder="e.g. Implement auth token refresh"
                autoFocus
                className="w-full bg-card border border-border-dim px-3 py-2 font-mono text-sm text-text-primary placeholder:text-text-muted focus:outline-none focus:border-amber-tac" />
            </div>
            {selectedDocs.length > 0 && (
              <div>
                <div className="font-mono text-xs text-text-muted tracking-widest mb-2">CONTEXT SOURCES</div>
                <div className="space-y-1">
                  {selectedDocs.map(d => (
                    <div key={d.uid} className="font-mono text-xs text-text-muted/70">
                      {d.source === "github" ? "⊙" : "◈"} {d.title ?? d.source_url}
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="font-mono text-xs text-text-muted/60 leading-relaxed">
              A GitHub issue will be created in each connected repository, labelled{" "}
              <span className="text-amber-tac">topgun-mission</span>, and a vault file saved to Drive.
            </div>
            {error && (
              <div className="font-mono text-xs text-red-alert border border-red-alert/30 px-3 py-2">{error}</div>
            )}
            <div className="flex justify-end gap-3">
              <button onClick={onClose}
                className="font-mono text-xs px-4 py-1.5 border border-border-dim text-text-muted hover:text-text-secondary tracking-widest">
                CANCEL
              </button>
              <button onClick={deploy} disabled={!title.trim() || creating}
                className="font-mono text-xs px-5 py-1.5 border border-amber-tac text-amber-tac hover:bg-amber-tac/10 tracking-widest disabled:opacity-40">
                {creating ? "DEPLOYING…" : "DEPLOY MISSION"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Intel Sources section ─────────────────────────────────────────────────────

function IntelSourcesSection({
  docs,
  loading,
  selectedUids,
  onToggle,
  onTagged,
}: {
  docs: IntelDocument[];
  loading: boolean;
  selectedUids: Set<string>;
  onToggle: (uid: string) => void;
  onTagged: () => void;
}) {
  const { getToken } = useToken();
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<IntelSearchResult[] | null>(null);
  const [searching, setSearching] = useState(false);

  const handleSearch = async () => {
    if (!searchQuery.trim()) { setSearchResults(null); return; }
    setSearching(true);
    try {
      const token = await getToken();
      setSearchResults(await searchIntel(token, searchQuery));
    } catch { /* silently ignore */ }
    finally { setSearching(false); }
  };

  const clearSearch = () => { setSearchQuery(""); setSearchResults(null); };

  return (
    <section>
      <div className="flex items-end justify-between mb-4">
        <SectionHeader
          label="INTEL SOURCES"
          description="Registered documents and auto-discovered issues. Check boxes to add to KB context."
          inline
        />
        <div className="flex gap-2 shrink-0 ml-4">
          {searchResults && (
            <button onClick={clearSearch}
              className="font-mono text-xs px-3 py-1.5 border border-border-dim text-text-muted hover:text-text-secondary tracking-widest">
              CLEAR
            </button>
          )}
          <input
            type="text"
            value={searchQuery}
            onChange={e => setSearchQuery(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleSearch()}
            placeholder="Search…"
            className="bg-card border border-border-dim px-3 py-1.5 font-mono text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-amber-tac w-40"
          />
          <button onClick={handleSearch} disabled={searching}
            className="font-mono text-xs px-3 py-1.5 border border-border-dim text-amber-tac hover:bg-card tracking-widest disabled:opacity-40">
            {searching ? "…" : "SEARCH"}
          </button>
        </div>
      </div>

      {searchResults !== null ? (
        <>
          <div className="font-mono text-xs text-text-muted tracking-widest mb-4">
            {searchResults.length} RESULT{searchResults.length !== 1 ? "S" : ""}
          </div>
          <IntelGrid
            docs={searchResults.map(r => ({ uid: r.uid, source: r.source, source_url: r.source_url, title: r.title }) as IntelDocument)}
            selectedUids={selectedUids}
            onToggle={onToggle}
            onTagged={onTagged}
          />
        </>
      ) : loading ? (
        <Spinner />
      ) : (
        <IntelGrid
          docs={docs}
          selectedUids={selectedUids}
          onToggle={onToggle}
          onTagged={onTagged}
        />
      )}
    </section>
  );
}

// ── Docs section ──────────────────────────────────────────────────────────────

function DocsSection() {
  return (
    <section id="docs">
      <SectionHeader label="DOCS" description="User guides, developer references, and platform documentation." />
      <Link
        to="/deck/docs"
        className="tac-border p-5 flex items-center justify-between hover:border-amber-tac/60 transition-colors group"
      >
        <div>
          <div className="font-mono text-xs text-text-primary tracking-wide">DOCUMENTATION</div>
          <div className="font-mono text-xs text-text-muted mt-1">
            User guides · Developer references · Platform architecture
          </div>
        </div>
        <span className="font-mono text-lg text-text-muted group-hover:text-amber-tac transition-colors">→</span>
      </Link>
    </section>
  );
}

// ── Intel Signal Board ────────────────────────────────────────────────────────

function IntelSignalBoard({ stats }: { stats: IntelStats }) {
  const { total, missions } = stats;
  const gh = stats.by_source.github;
  const obs = stats.by_source.obsidian;
  const backlog = total - missions;
  const coveragePct = total > 0 ? Math.round((missions / total) * 100) : 0;
  const ghPct = total > 0 ? (gh / total) * 100 : 0;
  const obsPct = total > 0 ? (obs / total) * 100 : 0;

  return (
    <div className="tac-border p-5 mt-6 animate-fadeIn">
      <div className="grid grid-cols-3 gap-8 items-start">

        {/* Total */}
        <div>
          <div className="font-mono text-4xl font-bold text-amber-tac tabular-nums">{total}</div>
          <div className="font-mono text-xs text-text-muted tracking-widest uppercase mt-1">Signals indexed</div>
          <div className="font-mono text-[10px] text-text-muted/50 mt-1">
            {gh} github · {obs} obsidian
          </div>
        </div>

        {/* Source mix */}
        <div>
          <div className="font-mono text-xs text-text-muted tracking-widest uppercase mb-3">Source mix</div>
          <div className="space-y-2.5">
            <div>
              <div className="flex justify-between items-center mb-1">
                <span className="font-mono text-xs text-green-live">GITHUB</span>
                <span className="font-mono text-xs text-text-muted tabular-nums">{gh}</span>
              </div>
              <div className="h-px bg-border-dim">
                <div className="h-px bg-green-live transition-all duration-700" style={{ width: `${ghPct}%` }} />
              </div>
            </div>
            <div>
              <div className="flex justify-between items-center mb-1">
                <span className="font-mono text-xs text-cyan-hud">OBSIDIAN</span>
                <span className="font-mono text-xs text-text-muted tabular-nums">{obs}</span>
              </div>
              <div className="h-px bg-border-dim">
                <div className="h-px bg-cyan-hud transition-all duration-700" style={{ width: `${obsPct}%` }} />
              </div>
            </div>
          </div>
        </div>

        {/* Mission coverage */}
        <div>
          <div className="font-mono text-xs text-text-muted tracking-widest uppercase mb-3">Mission coverage</div>
          <div className="font-mono text-4xl font-bold text-amber-tac tabular-nums">{coveragePct}%</div>
          <div className="h-px bg-border-dim mt-2">
            <div className="h-px bg-amber-tac transition-all duration-700" style={{ width: `${coveragePct}%` }} />
          </div>
          <div className="font-mono text-[10px] text-text-muted/50 mt-2">
            {missions} tagged · {backlog} backlog
          </div>
        </div>

      </div>
    </div>
  );
}

// ── Shared helpers ────────────────────────────────────────────────────────────

function SectionHeader({
  label,
  description,
  inline = false,
}: {
  label: string;
  description: string;
  inline?: boolean;
}) {
  if (inline) {
    return (
      <div>
        <div className="font-mono text-xs text-text-muted tracking-widest uppercase">{label}</div>
        <p className="font-mono text-xs text-text-muted/60 mt-0.5">{description}</p>
      </div>
    );
  }
  return (
    <div className="mb-5">
      <div className="flex items-center gap-3 mb-1">
        <div className="font-mono text-xs text-text-muted tracking-widest uppercase">{label}</div>
        <div className="flex-1 h-px bg-border-dim" />
      </div>
      <p className="font-mono text-xs text-text-muted/60">{description}</p>
    </div>
  );
}
