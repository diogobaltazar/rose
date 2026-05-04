import { useState, useEffect, useCallback } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useNavigate } from "react-router-dom";
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

async function initBackendAuth(token: string): Promise<string> {
  const r = await fetch(`${BASE}/connect/backend/init`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!r.ok) throw new Error("init failed");
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
  const { isAuthenticated, isLoading, getAccessTokenSilently, loginWithRedirect } = useAuth0();
  const navigate = useNavigate();
  const [status, setStatus] = useState<ConnectionStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) loginWithRedirect();
  }, [isAuthenticated, isLoading, loginWithRedirect]);

  const load = useCallback(async () => {
    try {
      let token = "";
      try { token = await getAccessTokenSilently(); } catch { /* dev */ }
      setStatus(await fetchConnections(token));
    } catch (e) {
      setError(String(e));
    }
  }, [getAccessTokenSilently]);

  useEffect(() => {
    if (isAuthenticated) load();
  }, [isAuthenticated, load]);

  // Re-load if we returned from OAuth callback
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("connected")) {
      window.history.replaceState({}, "", "/deck/connections");
      load();
    }
  }, [load]);

  const handleConnectBackend = async () => {
    setBusy(true);
    try {
      let token = "";
      try { token = await getAccessTokenSilently(); } catch { /* dev */ }
      const url = await initBackendAuth(token);
      window.open(url, "_blank");
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
      try { token = await getAccessTokenSilently(); } catch { /* dev */ }
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
          onClick={() => navigate("/deck")}
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
                {status?.backend.provider ? status.backend.provider.toUpperCase() : "NOT CONFIGURED"}
              </div>
              <div className="font-mono text-xs text-text-muted mt-1">
                {status?.backend.connected
                  ? "Connected — all user data stored here"
                  : "No storage backend connected"}
              </div>
            </div>

            {status?.backend.connected ? (
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
                CONNECT GDRIVE
              </button>
            )}
          </div>
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
