import { useState, useEffect, useCallback } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useNavigate } from "react-router-dom";
import { useToken } from "../hooks/useToken";
import NavBar from "../components/NavBar";
import HUDGrid from "../components/HUDGrid";

const BASE = "/api";

interface ConnectionStatus {
  backend: { provider: string; connected: boolean };
  services: { name: string; provider: string; account: string }[];
}

async function fetchConnections(token: string): Promise<ConnectionStatus> {
  const r = await fetch(`${BASE}/connect`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) throw new Error("fetch failed");
  return r.json();
}

async function initBackendAuth(token: string, clientId: string, clientSecret: string): Promise<string> {
  const params = new URLSearchParams({ client_id: clientId, client_secret: clientSecret });
  const r = await fetch(`${BASE}/connect/backend/init?${params}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) throw new Error(`init failed: ${await r.text()}`);
  const data = await r.json();
  return data.auth_url;
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
  const [showGdriveForm, setShowGdriveForm] = useState(false);
  const [gdriveClientId, setGdriveClientId] = useState("");
  const [gdriveClientSecret, setGdriveClientSecret] = useState("");

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

  useEffect(() => {
    if (isAuthenticated) load();
  }, [isAuthenticated, load]);

  // Re-load if we returned from OAuth callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("connected")) {
      window.history.replaceState({}, "", "/deck/settings");
      load();
    }
  }, [load]);

  const handleConnectBackend = async () => {
    if (!gdriveClientId || !gdriveClientSecret) {
      setShowGdriveForm(true);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const token = await getToken();
      const url = await initBackendAuth(token, gdriveClientId, gdriveClientSecret);
      window.open(url, "_blank");
      setShowGdriveForm(false);
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };

  const handleRemove = async (name: string) => {
    setBusy(true);
    try {
      let token = "";
      token = await getToken();
      await removeConnection(token, name);
      await load();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
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
          <h1 className="font-mono text-xl font-semibold">Connections</h1>
          <p className="font-mono text-xs text-text-muted mt-2">
            Connect external services to topgun. All credentials are encrypted.
          </p>
        </div>

        <button
          onClick={() => navigate("/deck/missions")}
          className="font-mono text-xs text-text-muted hover:text-amber-tac mb-8 block tracking-widest"
        >
          ← BACK TO DECK
        </button>

        {error && (
          <div className="tac-border p-4 mb-6">
            <p className="font-mono text-xs text-red-alert">{error}</p>
          </div>
        )}

        {/* Storage Backend */}
        <section className="mb-8">
          <div className="font-mono text-xs text-text-muted tracking-widest uppercase mb-4">
            Storage Backend
          </div>

          <div className="tac-border p-5 flex items-center justify-between">
            <div>
              <div className="font-mono text-xs text-text-primary">
                {status?.backend.connected ? "GOOGLE DRIVE" : "NOT CONFIGURED"}
              </div>
              <div className="font-mono text-xs text-text-muted mt-1">
                {status?.backend.connected
                  ? "Connected — all user data stored here"
                  : "No storage backend connected"}
              </div>
            </div>

            {!fetching && (status?.backend.connected ? (
              <button
                onClick={() => handleRemove("backend")}
                disabled={busy}
                className="font-mono text-xs px-4 py-1.5 border border-red-alert text-red-alert hover:bg-red-alert/10 tracking-widest"
              >
                DISCONNECT
              </button>
            ) : (
              <button
                onClick={handleConnectBackend}
                disabled={busy}
                className="font-mono text-xs px-4 py-1.5 border border-amber-tac text-amber-tac hover:bg-amber-tac/10 tracking-widest"
              >
                CONNECT
              </button>
            ))}
          </div>

          {showGdriveForm && !status?.backend.connected && (
            <div className="mt-4 space-y-3">
              <p className="font-mono text-xs text-text-muted">
                Enter your Google Cloud OAuth credentials (APIs &amp; Services → Credentials):
              </p>
              <input
                type="text"
                placeholder="Client ID  (.apps.googleusercontent.com)"
                value={gdriveClientId}
                onChange={e => setGdriveClientId(e.target.value)}
                className="w-full bg-card border border-border-dim px-3 py-1.5 font-mono text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-amber-tac"
              />
              <input
                type="password"
                placeholder="Client Secret"
                value={gdriveClientSecret}
                onChange={e => setGdriveClientSecret(e.target.value)}
                className="w-full bg-card border border-border-dim px-3 py-1.5 font-mono text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-amber-tac"
              />
              <div className="flex gap-2">
                <button
                  onClick={handleConnectBackend}
                  disabled={busy || !gdriveClientId || !gdriveClientSecret}
                  className="font-mono text-xs px-4 py-1.5 border border-amber-tac text-amber-tac hover:bg-amber-tac/10 tracking-widest disabled:opacity-40"
                >
                  AUTHORIZE
                </button>
                <button
                  onClick={() => setShowGdriveForm(false)}
                  className="font-mono text-xs px-4 py-1.5 border border-border-dim text-text-muted hover:text-text-secondary tracking-widest"
                >
                  CANCEL
                </button>
              </div>
            </div>
          )}

        </section>

        {/* Service Connections */}
        <section>
          <div className="font-mono text-xs text-text-muted tracking-widest uppercase mb-4">
            Service Connections
          </div>

          {!status?.backend.connected ? (
            <div className="tac-border p-6 text-center">
              <p className="font-mono text-xs text-text-muted">
                Connect a storage backend first to manage service connections.
              </p>
            </div>
          ) : status.services.length === 0 ? (
            <div className="tac-border p-6 text-center bracket-corners">
              <p className="font-mono text-xs text-text-muted tracking-widest">NO SERVICES CONNECTED</p>
              <p className="font-mono text-xs text-text-muted/60 mt-2">
                Use <span className="text-amber-tac">topgun config set github --name &lt;name&gt;</span> then{" "}
                <span className="text-amber-tac">topgun auth login --name &lt;name&gt;</span>
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {status.services.map((svc) => (
                <div key={svc.name} className="tac-border p-4 flex items-center justify-between">
                  <div>
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-xs px-2 py-0.5 border border-border-dim text-text-muted tracking-widest uppercase">
                        {svc.provider}
                      </span>
                      <span className="font-mono text-xs text-text-primary">{svc.name}</span>
                    </div>
                    {svc.account && (
                      <div className="font-mono text-xs text-text-muted mt-1">{svc.account}</div>
                    )}
                  </div>
                  <button
                    onClick={() => handleRemove(svc.name)}
                    disabled={busy}
                    className="font-mono text-xs px-3 py-1 border border-red-alert/40 text-red-alert/60 hover:border-red-alert hover:text-red-alert tracking-widest"
                  >
                    REMOVE
                  </button>
                </div>
              ))}
            </div>
          )}
        </section>
      </main>
    </div>
  );
}
