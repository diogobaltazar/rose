import { useState, useEffect, useCallback } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useNavigate } from "react-router-dom";
import { useToken } from "../hooks/useToken";
import NavBar from "../components/NavBar";
import HUDGrid from "../components/HUDGrid";
import { addGithubRepo, removeGithubRepo } from "../api";

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

interface GithubRepo { name: string; repo: string; authenticated: boolean; }
interface ConnectionStatus {
  backend: { provider: string; connected: boolean };
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
      const token = await getToken();
      setStatus(await fetchConnections(token));
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

        {/* ── Storage Backend ───────────────────────────── */}
        <section className="mb-8">
          <div className="font-mono text-xs text-text-muted tracking-widest uppercase mb-4">Storage Backend</div>
          <div className="tac-border p-5 flex items-center justify-between">
            <div>
              <div className="font-mono text-xs text-text-primary">
                {status?.backend.connected ? "GOOGLE DRIVE" : "NOT CONFIGURED"}
              </div>
              <div className="font-mono text-xs text-text-muted mt-1">
                {status?.backend.connected ? "Connected — all user data stored here" : "No storage backend connected"}
              </div>
            </div>
            {!fetching && (status?.backend.connected ? (
              <button onClick={() => handleRemove("backend")} disabled={busy}
                className="font-mono text-xs px-4 py-1.5 border border-red-alert text-red-alert hover:bg-red-alert/10 tracking-widest">
                DISCONNECT
              </button>
            ) : (
              <button onClick={handleConnectBackend} disabled={busy}
                className="font-mono text-xs px-4 py-1.5 border border-amber-tac text-amber-tac hover:bg-amber-tac/10 tracking-widest">
                CONNECT
              </button>
            ))}
          </div>
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
          <div className="flex items-center justify-between mb-4">
            <div className="font-mono text-xs text-text-muted tracking-widest uppercase">GitHub Repositories</div>
            {status?.backend.connected && !showGhForm && (
              <button onClick={() => setShowGhForm(true)}
                className="font-mono text-xs px-3 py-1 border border-amber-tac/40 text-amber-tac/60 hover:border-amber-tac hover:text-amber-tac tracking-widest">
                + ADD
              </button>
            )}
          </div>

          {!status?.backend.connected ? (
            <div className="tac-border p-6 text-center">
              <p className="font-mono text-xs text-text-muted">Connect a storage backend first.</p>
            </div>
          ) : (
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
          )}
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
    </div>
  );
}
