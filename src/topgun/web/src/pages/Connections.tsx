import { useState, useEffect, useCallback } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useNavigate } from "react-router-dom";
import { useToken } from "../hooks/useToken";
import NavBar from "../components/NavBar";
import HUDGrid from "../components/HUDGrid";
import { addGithubRepo, removeGithubRepo, saveLlmConfig, fetchLlmConfig, verifyLlmConfig } from "../api";
import ChatDialog from "../components/ChatDialog";
import ProviderPicker from "../components/ProviderPicker";

// ── Provider catalogues ───────────────────────────────────────────────────────

const LLM_PROVIDERS = [
  { id: "anthropic",  name: "Anthropic",     detail: "Claude Haiku · Sonnet · Opus",  available: true },
  { id: "openai",     name: "OpenAI",        detail: "GPT-4o · o1 · o3",              available: false },
  { id: "google",     name: "Google",        detail: "Gemini 2.5 Pro · Flash",         available: false },
  { id: "mistral",    name: "Mistral",       detail: "Large · Codestral",              available: false },
  { id: "av-llm",     name: "ALMA VICTORIA", detail: "Managed · Zero configuration",  available: false, enterprise: true },
];

const STORAGE_PROVIDERS = [
  { id: "gdrive",     name: "Google Drive",  detail: "Per-user encrypted storage",    available: true },
  { id: "icloud",     name: "iCloud Drive",  detail: "Apple CloudKit",                available: false },
  { id: "s3",         name: "AWS S3",        detail: "Bucket-based storage",          available: false },
  { id: "av-storage", name: "ALMA VICTORIA", detail: "Managed · Zero configuration",  available: false, enterprise: true },
];

const INTEL_SOURCES = [
  { id: "github",    name: "GitHub",        detail: "Issues · PRs · Discussions",    available: true },
  { id: "gdrive",    name: "Google Drive",  detail: "Docs · Sheets · Slides",        available: true },
  { id: "mcp",       name: "MCP Server",    detail: "Any MCP-compatible data source",available: false },
  { id: "gitlab",    name: "GitLab",        detail: "Issues · MRs",                  available: false },
  { id: "notion",    name: "Notion",        detail: "Pages · Databases",             available: false },
  { id: "icloud",    name: "iCloud",        detail: "Notes · Drive",                 available: false },
  { id: "av-intel",  name: "ALMA VICTORIA", detail: "Managed · Zero configuration",  available: false, enterprise: true },
];

// ── GitHub token verification ─────────────────────────────────────────────────

type CheckStatus = "pending" | "checking" | "ok" | "fail";
interface Check { label: string; status: CheckStatus; detail?: string; }

async function verifyGithubToken(
  repo: string,
  pat: string,
  onUpdate: (checks: Check[]) => void,
): Promise<boolean> {
  const headers = { Authorization: `Bearer ${pat}`, Accept: "application/vnd.github+json" };
  const checks: Check[] = [
    { label: "Authenticating token", status: "pending" },
    { label: "Checking repository access", status: "pending" },
    { label: "Verifying push permission", status: "pending" },
    { label: "Verifying issues permission", status: "pending" },
  ];
  const set = (i: number, patch: Partial<Check>) => {
    checks[i] = { ...checks[i], ...patch };
    onUpdate([...checks]);
  };

  set(0, { status: "checking" });
  try {
    const r = await fetch("https://api.github.com/user", { headers });
    if (!r.ok) { set(0, { status: "fail", detail: "Invalid or expired token" }); return false; }
    const u = await r.json();
    set(0, { status: "ok", detail: u.login });
  } catch { set(0, { status: "fail", detail: "Could not reach GitHub API" }); return false; }

  set(1, { status: "checking" });
  let permissions: Record<string, boolean> = {};
  try {
    const r = await fetch(`https://api.github.com/repos/${repo}`, { headers });
    if (!r.ok) {
      set(1, { status: "fail", detail: r.status === 404 ? "Repository not found" : "Access denied" });
      return false;
    }
    const data = await r.json();
    permissions = data.permissions ?? {};
    set(1, { status: "ok", detail: data.full_name });
  } catch { set(1, { status: "fail", detail: "Repository check failed" }); return false; }

  set(2, { status: "checking" });
  if (!permissions.push) {
    set(2, { status: "fail", detail: "Push access required for commits and PRs" });
    return false;
  }
  set(2, { status: "ok", detail: "Commits, pushes, and PRs allowed" });

  set(3, { status: "checking" });
  try {
    const r = await fetch(`https://api.github.com/repos/${repo}/issues?per_page=1`, { headers });
    if (!r.ok) { set(3, { status: "fail", detail: "Cannot read issues" }); return false; }
    set(3, { status: "ok" });
  } catch { set(3, { status: "fail", detail: "Issues check failed" }); return false; }

  return true;
}

function CheckRow({ check }: { check: Check }) {
  const icon =
    check.status === "ok" ? "✓" :
    check.status === "fail" ? "✗" :
    check.status === "checking" ? "·" : "·";
  const colour =
    check.status === "ok" ? "text-green-live" :
    check.status === "fail" ? "text-red-alert" :
    check.status === "checking" ? "text-amber-tac animate-pulse_amber" :
    "text-text-muted";
  return (
    <div className="flex items-baseline gap-3">
      <span className={`font-mono text-xs w-3 shrink-0 ${colour}`}>{icon}</span>
      <span className={`font-mono text-xs ${check.status === "pending" ? "text-text-muted/40" : "text-text-primary"}`}>
        {check.label}
      </span>
      {check.detail && (
        <span className={`font-mono text-xs ml-auto ${check.status === "fail" ? "text-red-alert" : "text-text-muted"}`}>
          {check.detail}
        </span>
      )}
    </div>
  );
}

const BASE = "/api";

// ── Proxy header field ────────────────────────────────────────────────────────

const KNOWN_PROXY_HEADERS = ["x-api-key", "x-goog-api-key", "api-key"];

function ProxyHeaderField({ header, value, onHeaderChange, onValueChange }: { header: string; value: string; onHeaderChange: (v: string) => void; onValueChange: (v: string) => void; }) {
  const isKnown = KNOWN_PROXY_HEADERS.includes(header);
  const selectVal = header === "" ? "" : isKnown ? header : "__custom__";
  const handleSelect = (v: string) => { if (v === "") onHeaderChange(""); else if (v === "__custom__") onHeaderChange(" "); else onHeaderChange(v); };
  return (
    <div className="space-y-2 pl-2 border-l border-border-dim">
      <div className="font-mono text-xs text-text-muted">Proxy header name</div>
      <select value={selectVal} onChange={e => handleSelect(e.target.value)} className="w-full bg-card border border-border-dim px-3 py-1.5 font-mono text-xs text-text-primary focus:outline-none focus:border-amber-tac">
        <option value="">— none —</option>
        {KNOWN_PROXY_HEADERS.map(h => <option key={h} value={h}>{h}</option>)}
        <option value="__custom__">Custom…</option>
      </select>
      {!isKnown && header !== "" && <input type="text" placeholder="Custom header name" value={header.trim()} onChange={e => onHeaderChange(e.target.value)} className="w-full bg-card border border-border-dim px-3 py-1.5 font-mono text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-amber-tac" />}
      <input type="text" placeholder="Header value (e.g. claude)" value={value} onChange={e => onValueChange(e.target.value)} className="w-full bg-card border border-border-dim px-3 py-1.5 font-mono text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-amber-tac" />
    </div>
  );
}

// ── Help icon ─────────────────────────────────────────────────────────────────
function HelpIcon({ onClick }: { onClick: () => void }) {
  return (
    <button onClick={onClick}
      className="font-mono text-xs w-5 h-5 border border-amber-tac/40 text-amber-tac/60 hover:border-amber-tac hover:text-amber-tac flex items-center justify-center transition-colors"
      title="Ask AI assistant">?</button>
  );
}

interface GithubRepo { name: string; repo: string; authenticated: boolean; }
interface ConnectionStatus {
  backend: { provider: string; connected: boolean };
  llm: { connected: boolean };
  services: { name: string; provider: string; account: string }[];
  github_repos: GithubRepo[];
}

async function fetchConnections(token: string): Promise<ConnectionStatus> {
  const r = await fetch(`${BASE}/connect`, { headers: { Authorization: `Bearer ${token}` } });
  if (!r.ok) throw new Error("fetch failed");
  return r.json();
}

async function initBackendAuth(token: string, clientId: string, clientSecret: string): Promise<string> {
  const params = new URLSearchParams({ client_id: clientId, client_secret: clientSecret });
  const r = await fetch(`${BASE}/connect/backend/init?${params}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) throw new Error(`init failed: ${await r.text()}`);
  return (await r.json()).auth_url;
}

async function removeConnection(token: string, name: string): Promise<void> {
  const r = await fetch(`${BASE}/connect/${encodeURIComponent(name)}`, {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) throw new Error("remove failed");
}

export default function Connections() {
  const { isAuthenticated, isLoading, loginWithRedirect } = useAuth0();
  const { getToken } = useToken();
  const navigate = useNavigate();
  const [status, setStatus] = useState<ConnectionStatus | null>(null);
  const [fetching, setFetching] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [token, setToken] = useState<string>("");

  // LLM form
  const [showLlmForm, setShowLlmForm] = useState(false);
  const [llmApiKey, setLlmApiKey] = useState("");
  const [llmBaseUrl, setLlmBaseUrl] = useState("");
  const [llmProxyHeader, setLlmProxyHeader] = useState("");
  const [llmProxyValue, setLlmProxyValue] = useState("");
  const [llmBusy, setLlmBusy] = useState(false);
  const [llmChecks, setLlmChecks] = useState<Check[] | null>(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Provider selection
  const [selectedLlm, setSelectedLlm] = useState("anthropic");
  const [selectedBackend, setSelectedBackend] = useState("gdrive");
  const [selectedIntelSource, setSelectedIntelSource] = useState("github");

  // Chat dialog
  const [chat, setChat] = useState<{ question: string; title: string } | null>(null);

  // GDrive form
  const [showGdriveForm, setShowGdriveForm] = useState(false);
  const [gdriveClientId, setGdriveClientId] = useState("");
  const [gdriveClientSecret, setGdriveClientSecret] = useState("");

  // GitHub repo form
  const [showGhForm, setShowGhForm] = useState(false);
  const [ghName, setGhName] = useState("");
  const [ghRepo, setGhRepo] = useState("");
  const [ghPat, setGhPat] = useState("");
  const [ghChecks, setGhChecks] = useState<Check[] | null>(null);
  const [ghVerifying, setGhVerifying] = useState(false);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) loginWithRedirect();
  }, [isAuthenticated, isLoading, loginWithRedirect]);

  const load = useCallback(async () => {
    setFetching(true);
    try {
      const tok = await getToken();
      setToken(tok);
      setStatus(await fetchConnections(tok));
    } catch (e) {
      setError(String(e));
    } finally {
      setFetching(false);
    }
  }, [getToken]);

  useEffect(() => { if (isAuthenticated) load(); }, [isAuthenticated, load]);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("connected")) {
      window.history.replaceState({}, "", "/deck/settings");
      load();
    }
  }, [load]);

  const resetLlmForm = () => {
    setShowLlmForm(false); setShowAdvanced(false); setLlmChecks(null);
    setLlmApiKey(""); setLlmBaseUrl(""); setLlmProxyHeader(""); setLlmProxyValue("");
  };

  const handleSaveLlm = async () => {
    if (!llmApiKey) return;
    const cfg = { api_key: llmApiKey, base_url: llmBaseUrl, proxy_header: llmProxyHeader.trim(), proxy_value: llmProxyValue };
    setLlmBusy(true); setError(null);
    setLlmChecks([
      { label: "Connecting to provider", status: "checking" },
      { label: "Verifying credentials", status: "pending" },
      { label: "Saving credentials", status: "pending" },
    ]);
    const set = (i: number, patch: Partial<Check>) =>
      setLlmChecks(prev => prev ? prev.map((c, j) => j === i ? { ...c, ...patch } : c) : prev);
    try {
      const tok = await getToken();
      set(0, { status: "ok", detail: cfg.base_url || "api.anthropic.com" });
      set(1, { status: "checking" });
      await verifyLlmConfig(tok, cfg);
      set(1, { status: "ok", detail: "Authenticated" });
      set(2, { status: "checking" });
      await saveLlmConfig(tok, cfg);
      set(2, { status: "ok", detail: "Encrypted and stored" });
      await new Promise(r => setTimeout(r, 800));
      resetLlmForm();
      await load();
    } catch (e) {
      const msg = String(e).replace(/^Error:\s*/, "");
      setLlmChecks(prev => {
        if (!prev) return prev;
        const idx = prev.findIndex(c => c.status === "checking" || c.status === "pending");
        return prev.map((c, i) => i === (idx >= 0 ? idx : 1) ? { ...c, status: "fail", detail: msg } : c);
      });
    } finally { setLlmBusy(false); }
  };

  const handleConnectBackend = async () => {
    if (!gdriveClientId || !gdriveClientSecret) { setShowGdriveForm(true); return; }
    setBusy(true); setError(null);
    try {
      const token = await getToken();
      window.open(await initBackendAuth(token, gdriveClientId, gdriveClientSecret), "_blank");
      setShowGdriveForm(false);
    } catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  };

  const handleRemove = async (name: string) => {
    setBusy(true);
    try { await removeConnection(await getToken(), name); await load(); }
    catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  };

  const resetGhForm = () => {
    setGhName(""); setGhRepo(""); setGhPat("");
    setGhChecks(null); setGhVerifying(false);
    setShowGhForm(false);
  };

  const handleAddGhRepo = async () => {
    if (!ghName || !ghRepo || !ghPat) return;
    const repo = ghRepo.replace(/^https?:\/\/github\.com\//, "").replace(/\/$/, "");
    setGhVerifying(true);
    setGhChecks([
      { label: "Authenticating token", status: "pending" },
      { label: "Checking repository access", status: "pending" },
      { label: "Verifying push permission", status: "pending" },
      { label: "Verifying issues permission", status: "pending" },
    ]);
    const ok = await verifyGithubToken(repo, ghPat, setGhChecks);
    if (!ok) { setGhVerifying(false); return; }
    // All checks passed — save
    setGhChecks(prev => prev ? [...prev, { label: "Saving credentials", status: "checking" }] : prev);
    try {
      await addGithubRepo(await getToken(), ghName, repo, ghPat);
      setGhChecks(prev => prev ? [...prev.slice(0, -1), { label: "Saving credentials", status: "ok", detail: "Encrypted and stored" }] : prev);
      await new Promise(r => setTimeout(r, 800));
      resetGhForm();
      await load();
    } catch (e) {
      setGhChecks(prev => prev ? [...prev.slice(0, -1), { label: "Saving credentials", status: "fail", detail: String(e) }] : prev);
    }
    setGhVerifying(false);
  };

  const handleRemoveGhRepo = async (name: string) => {
    setBusy(true);
    try { await removeGithubRepo(await getToken(), name); await load(); }
    catch (e) { setError(String(e)); }
    finally { setBusy(false); }
  };

  if (isLoading || (!isAuthenticated && !error)) {
    return (
      <div className="min-h-screen bg-base flex items-center justify-center">
        <span className="font-mono text-xs text-amber-tac animate-pulse_amber tracking-widest">LOADING...</span>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-base text-text-primary">
      <HUDGrid />
      <NavBar />
      <main className="relative z-10 max-w-3xl mx-auto px-6 py-10">

        <div className="mb-8">
          <div className="font-mono text-xs text-amber-tac tracking-[0.4em] uppercase mb-1">Command Deck</div>
          <h1 className="font-mono text-xl font-semibold">Settings</h1>
          <p className="font-mono text-xs text-text-muted mt-2">Connect external services. All credentials are encrypted.</p>
        </div>

        <button onClick={() => navigate("/deck/missions")}
          className="font-mono text-xs text-text-muted hover:text-amber-tac mb-8 block tracking-widest">
          ← BACK TO DECK
        </button>

        {error && (
          <div className="tac-border p-4 mb-6">
            <p className="font-mono text-xs text-red-alert">{error}</p>
          </div>
        )}

        {/* ── AI Provider ───────────────────────────────── */}
        <section className="mb-8">
          <div className="flex items-center gap-2 mb-1">
            <div className="font-mono text-xs text-text-muted tracking-widest uppercase">AI Provider</div>
          </div>
          <p className="font-mono text-xs text-text-muted/70 mb-4 leading-relaxed">
            Powers the AI assistant available throughout the platform. Your API key is encrypted and stored per user.
          </p>
          <ProviderPicker providers={LLM_PROVIDERS} selected={selectedLlm} onSelect={setSelectedLlm} />
          {fetching ? (
            <div className="tac-border p-5 flex items-center justify-between">
              <div><div className="font-mono text-xs text-amber-tac animate-pulse_amber tracking-widest">CHECKING…</div></div>
              <span className="font-mono text-xs text-amber-tac animate-pulse_amber tracking-widest">···</span>
            </div>
          ) : (
            <div className="tac-border p-5 flex items-center justify-between">
              <div>
                <div className="font-mono text-xs text-text-primary">{status?.llm?.connected ? "ANTHROPIC" : "NOT CONFIGURED"}</div>
                <div className="font-mono text-xs text-text-muted mt-1">
                  {status?.llm?.connected ? "AI assistant active — click ? on any section to ask questions" : "Configure an API key to enable the AI assistant"}
                </div>
              </div>
              {status?.llm?.connected ? (
                <div className="flex gap-2">
                  <button onClick={async () => {
                    setShowLlmForm(v => !v);
                    if (!showLlmForm) {
                      try {
                        const cfg = await fetchLlmConfig(await getToken());
                        setLlmApiKey(cfg.api_key ?? ""); setLlmBaseUrl(cfg.base_url ?? "");
                        setLlmProxyHeader(cfg.proxy_header ?? ""); setLlmProxyValue(cfg.proxy_value ?? "");
                        if (cfg.proxy_header || cfg.proxy_value) setShowAdvanced(true);
                      } catch { /* leave blank */ }
                    }
                  }} disabled={busy} className="font-mono text-xs px-4 py-1.5 border border-amber-tac/40 text-amber-tac/60 hover:border-amber-tac hover:text-amber-tac tracking-widest">UPDATE</button>
                  <button onClick={() => handleRemove("llm")} disabled={busy} className="font-mono text-xs px-4 py-1.5 border border-red-alert text-red-alert hover:bg-red-alert/10 tracking-widest">DISCONNECT</button>
                </div>
              ) : (
                <button onClick={() => setShowLlmForm(true)} disabled={busy} className="font-mono text-xs px-4 py-1.5 border border-amber-tac text-amber-tac hover:bg-amber-tac/10 tracking-widest">CONNECT</button>
              )}
            </div>
          )}
          {showLlmForm && (
            <div className="mt-4 space-y-3">
              {llmChecks ? (
                <>
                  <p className="font-mono text-xs text-text-muted tracking-widest uppercase mb-1">Verifying</p>
                  <div className="space-y-2">{llmChecks.map((c, i) => <CheckRow key={i} check={c} />)}</div>
                  {!llmBusy && llmChecks.some(c => c.status === "fail") && (
                    <button onClick={() => setLlmChecks(null)} className="font-mono text-xs px-3 py-1 border border-border-dim text-text-muted hover:text-amber-tac tracking-widest mt-2">← EDIT</button>
                  )}
                </>
              ) : (
                <>
                  <p className="font-mono text-xs text-text-muted">Enter your API key. Credentials are verified before saving.</p>
                  <input type="password" placeholder="API key (sk-ant-… or Bearer token)" value={llmApiKey} onChange={e => setLlmApiKey(e.target.value)} className="w-full bg-card border border-border-dim px-3 py-1.5 font-mono text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-amber-tac" />
                  <input type="text" placeholder="Base URL (optional — leave blank for api.anthropic.com)" value={llmBaseUrl} onChange={e => setLlmBaseUrl(e.target.value)} className="w-full bg-card border border-border-dim px-3 py-1.5 font-mono text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-amber-tac" />
                  <button onClick={() => setShowAdvanced(v => !v)} className="font-mono text-xs text-text-muted hover:text-amber-tac tracking-widest">{showAdvanced ? "▲ HIDE ADVANCED" : "▼ ADVANCED (proxy headers)"}</button>
                  {showAdvanced && <ProxyHeaderField header={llmProxyHeader} value={llmProxyValue} onHeaderChange={setLlmProxyHeader} onValueChange={setLlmProxyValue} />}
                  <div className="flex gap-2">
                    <button onClick={handleSaveLlm} disabled={llmBusy || !llmApiKey} className="font-mono text-xs px-4 py-1.5 border border-amber-tac text-amber-tac hover:bg-amber-tac/10 tracking-widest disabled:opacity-40">VERIFY &amp; SAVE</button>
                    <button onClick={resetLlmForm} className="font-mono text-xs px-4 py-1.5 border border-border-dim text-text-muted hover:text-text-secondary tracking-widest">CANCEL</button>
                  </div>
                </>
              )}
            </div>
          )}
        </section>

        {/* ── Storage Backend ───────────────────────────── */}
        <section className="mb-8">
          <div className="flex items-center gap-2 mb-1">
            <div className="font-mono text-xs text-text-muted tracking-widest uppercase">Storage Backend</div>
            {status?.llm?.connected && !fetching && <HelpIcon onClick={() => setChat({ question: "How does the Storage Backend work in ALMA VICTORIA TOPGUN? What is Google Drive used for and how do I set it up?", title: "Storage Backend" })} />}
          </div>
          <p className="font-mono text-xs text-text-muted/70 mb-4 leading-relaxed">
            Where all your data lives — missions, timers, configuration, and intel. You supply the OAuth credentials from your own cloud project so you remain in full control of your data.
          </p>
          <ProviderPicker providers={STORAGE_PROVIDERS} selected={selectedBackend} onSelect={setSelectedBackend} />
          {fetching ? (
            <div className="tac-border p-5 flex items-center justify-between">
              <div>
                <div className="font-mono text-xs text-amber-tac animate-pulse_amber tracking-widest">
                  CONNECTING TO GOOGLE DRIVE…
                </div>
                <div className="font-mono text-xs text-text-muted mt-1">
                  drive.google.com · verifying credentials
                </div>
              </div>
              <span className="font-mono text-xs text-amber-tac animate-pulse_amber tracking-widest">···</span>
            </div>
          ) : (
          <div className="tac-border p-5 flex items-center justify-between">
            <div>
              <div className="font-mono text-xs text-text-primary">
                {status?.backend.connected ? "GOOGLE DRIVE" : "NOT CONFIGURED"}
              </div>
              <div className="font-mono text-xs text-text-muted mt-1">
                {status?.backend.connected ? "Connected — all user data stored here" : "No storage backend connected"}
              </div>
            </div>
            {status?.backend.connected ? (
              <button onClick={() => handleRemove("backend")} disabled={busy}
                className="font-mono text-xs px-4 py-1.5 border border-red-alert text-red-alert hover:bg-red-alert/10 tracking-widest">
                DISCONNECT
              </button>
            ) : (
              <button onClick={handleConnectBackend} disabled={busy}
                className="font-mono text-xs px-4 py-1.5 border border-amber-tac text-amber-tac hover:bg-amber-tac/10 tracking-widest">
                CONNECT
              </button>
            )}
          </div>
          )}
          {showGdriveForm && !status?.backend.connected && (
            <div className="mt-4 space-y-3">
              <p className="font-mono text-xs text-text-muted">
                Enter your Google Cloud OAuth credentials (APIs &amp; Services → Credentials):
              </p>
              <input type="text" placeholder="Client ID (.apps.googleusercontent.com)"
                value={gdriveClientId} onChange={e => setGdriveClientId(e.target.value)}
                className="w-full bg-card border border-border-dim px-3 py-1.5 font-mono text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-amber-tac" />
              <input type="password" placeholder="Client Secret"
                value={gdriveClientSecret} onChange={e => setGdriveClientSecret(e.target.value)}
                className="w-full bg-card border border-border-dim px-3 py-1.5 font-mono text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-amber-tac" />
              <div className="flex gap-2">
                <button onClick={handleConnectBackend} disabled={busy || !gdriveClientId || !gdriveClientSecret}
                  className="font-mono text-xs px-4 py-1.5 border border-amber-tac text-amber-tac hover:bg-amber-tac/10 tracking-widest disabled:opacity-40">
                  AUTHORIZE
                </button>
                <button onClick={() => setShowGdriveForm(false)}
                  className="font-mono text-xs px-4 py-1.5 border border-border-dim text-text-muted hover:text-text-secondary tracking-widest">
                  CANCEL
                </button>
              </div>
            </div>
          )}
        </section>

        {/* ── GitHub Repositories ───────────────────────── */}
        <section className="mb-8">
          <div className="flex items-center gap-2 mb-1">
            <div className="font-mono text-xs text-text-muted tracking-widest uppercase">Intel Knowledge Base Sources</div>
            {status?.llm?.connected && !fetching && <HelpIcon onClick={() => setChat({ question: "What is the Intel Knowledge Base in ALMA VICTORIA TOPGUN? How do intel sources work and what gets imported?", title: "Intel Knowledge Base" })} />}
          </div>
          <p className="font-mono text-xs text-text-muted/70 mb-4 leading-relaxed">
            Connect the external sources that feed your Intel deck — issues, documents, and knowledge that the autonomous agents use as mission context.
          </p>
          <ProviderPicker providers={INTEL_SOURCES} selected={selectedIntelSource} onSelect={id => { setSelectedIntelSource(id); setShowGhForm(false); setGhChecks(null); }} />
          {!fetching && status?.backend.connected && selectedIntelSource === "github" && !showGhForm && (
            <div className="flex justify-end mb-2">
              <button onClick={() => setShowGhForm(true)} className="font-mono text-xs px-3 py-1 border border-amber-tac/40 text-amber-tac/60 hover:border-amber-tac hover:text-amber-tac tracking-widest">+ ADD</button>
            </div>
          )}

          {fetching ? (
            <div className="tac-border p-4 flex items-center justify-between">
              <div className="font-mono text-xs text-amber-tac animate-pulse_amber tracking-widest">LOADING…</div>
              <span className="font-mono text-xs text-amber-tac animate-pulse_amber tracking-widest">···</span>
            </div>
          ) : !status?.backend.connected ? (
            <div className="tac-border p-6 text-center"><p className="font-mono text-xs text-text-muted">Connect a storage backend first.</p></div>
          ) : selectedIntelSource === "gdrive" ? (
            <div className="tac-border p-5 flex items-center justify-between">
              <div>
                <div className="font-mono text-xs text-text-primary">{status?.backend.connected ? "GOOGLE DRIVE" : "NOT CONNECTED"}</div>
                <div className="font-mono text-xs text-text-muted mt-1">{status?.backend.connected ? "Documents in your topgun/ Drive folder are available as intel sources" : "Connect Google Drive as your storage backend first"}</div>
              </div>
              {status?.backend.connected && <span className="font-mono text-[10px] text-green-live border border-green-live/30 px-2 py-0.5 tracking-widest">ACTIVE</span>}
            </div>
          ) : selectedIntelSource === "github" ? (
            <>
              {showGhForm && (
                <div className="tac-border p-4 mb-3 space-y-3">
                  {!ghVerifying && !ghChecks ? (
                    <>
                      <p className="font-mono text-xs text-text-muted">
                        Issues from this repo will appear in Intel. Token is verified before saving.
                      </p>
                      <input type="text" placeholder="Connection name (e.g. my-project)"
                        value={ghName} onChange={e => setGhName(e.target.value)}
                        className="w-full bg-card border border-border-dim px-3 py-1.5 font-mono text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-amber-tac" />
                      <input type="text" placeholder="Repository (owner/repo or full GitHub URL)"
                        value={ghRepo} onChange={e => setGhRepo(e.target.value)}
                        className="w-full bg-card border border-border-dim px-3 py-1.5 font-mono text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-amber-tac" />
                      <input type="password" placeholder="Personal Access Token"
                        value={ghPat} onChange={e => setGhPat(e.target.value)}
                        className="w-full bg-card border border-border-dim px-3 py-1.5 font-mono text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-amber-tac" />
                      <div className="flex gap-2">
                        <button onClick={handleAddGhRepo} disabled={!ghName || !ghRepo || !ghPat}
                          className="font-mono text-xs px-4 py-1.5 border border-amber-tac text-amber-tac hover:bg-amber-tac/10 tracking-widest disabled:opacity-40">
                          CONNECT
                        </button>
                        <button onClick={resetGhForm}
                          className="font-mono text-xs px-4 py-1.5 border border-border-dim text-text-muted hover:text-text-secondary tracking-widest">
                          CANCEL
                        </button>
                      </div>
                    </>
                  ) : (
                    <>
                      <p className="font-mono text-xs text-text-muted tracking-widest uppercase mb-1">Verifying</p>
                      <div className="space-y-2">
                        {(ghChecks ?? []).map((c, i) => <CheckRow key={i} check={c} />)}
                      </div>
                      {!ghVerifying && ghChecks?.some(c => c.status === "fail") && (
                        <button onClick={() => setGhChecks(null)}
                          className="font-mono text-xs px-3 py-1 border border-border-dim text-text-muted hover:text-amber-tac tracking-widest mt-2">
                          ← EDIT
                        </button>
                      )}
                    </>
                  )}
                </div>
              )}

              {(status?.github_repos ?? []).length === 0 && !showGhForm ? (
                <div className="tac-border p-6 text-center">
                  <p className="font-mono text-xs text-text-muted tracking-widest">NO REPOSITORIES CONNECTED</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {(status?.github_repos ?? []).map(r => (
                    <div key={r.name} className="tac-border p-4 flex items-center justify-between">
                      <div>
                        <div className="flex items-center gap-3">
                          <span className="font-mono text-xs px-2 py-0.5 border border-border-dim text-text-muted tracking-widest uppercase">GH</span>
                          <span className="font-mono text-xs text-text-primary">{r.repo}</span>
                        </div>
                        <div className="font-mono text-xs text-text-muted mt-1">{r.name}</div>
                      </div>
                      <button onClick={() => handleRemoveGhRepo(r.name)} disabled={busy}
                        className="font-mono text-xs px-3 py-1 border border-red-alert/40 text-red-alert/60 hover:border-red-alert hover:text-red-alert tracking-widest">
                        DISCONNECT
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </>
          ) : null}
        </section>

        {/* ── Service Connections (legacy) ──────────────── */}
        {(status?.services ?? []).length > 0 && (
          <section>
            <div className="font-mono text-xs text-text-muted tracking-widest uppercase mb-4">Service Connections</div>
            <div className="space-y-2">
              {(status?.services ?? []).map(svc => (
                <div key={svc.name} className="tac-border p-4 flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-xs px-2 py-0.5 border border-border-dim text-text-muted tracking-widest uppercase">{svc.provider}</span>
                      <span className="font-mono text-xs text-text-primary">{svc.name}</span>
                    </div>
                    {svc.account && <div className="font-mono text-xs text-text-muted mt-1">{svc.account}</div>}
                  </div>
                  <button onClick={() => handleRemove(svc.name)} disabled={busy}
                    className="font-mono text-xs px-3 py-1 border border-red-alert/40 text-red-alert/60 hover:border-red-alert hover:text-red-alert tracking-widest">
                    REMOVE
                  </button>
                </div>
              ))}
            </div>
          </section>
        )}
      </main>

      {chat && token && (
        <ChatDialog presetQuestion={chat.question} componentTitle={chat.title} token={token} onClose={() => setChat(null)} />
      )}
    </div>
  );
}
