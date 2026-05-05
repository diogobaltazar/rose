import { useState, useEffect } from "react";
import { Auth0Provider, useAuth0 } from "@auth0/auth0-react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import Landing from "./pages/Landing";
import Callback from "./pages/Callback";
import MissionDeck from "./pages/MissionDeck";
import IntelDeck from "./pages/IntelDeck";
import Pilots from "./pages/Pilots";
import Connections from "./pages/Connections";
import Mission from "./pages/Mission";
import Sortie from "./pages/Sortie";
import Logbook from "./pages/Logbook";
import { getConfig, getIntelStats, getIntelList } from "./api";
import { useToken } from "./hooks/useToken";
import { EngagementProvider } from "./context/EngagementContext";
import type { AppConfig } from "./types";

function PrefetchOnAuth() {
  const { isAuthenticated } = useAuth0();
  const { getToken } = useToken();
  useEffect(() => {
    if (!isAuthenticated) return;
    getToken().then(token => {
      getIntelStats(token).catch(() => {});
      getIntelList(token).catch(() => {});
    });
  }, [isAuthenticated, getToken]);
  return null;
}

export default function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [configError, setConfigError] = useState(false);

  useEffect(() => {
    getConfig()
      .then(setConfig)
      .catch(() => {
        // Dev fallback: read from env vars set by vite
        const env = (import.meta as unknown as { env: Record<string, string> }).env ?? {};
        const domain = env.VITE_AUTH0_DOMAIN;
        const clientId = env.VITE_AUTH0_CLIENT_ID;
        const audience = env.VITE_AUTH0_AUDIENCE;
        if (domain && clientId) {
          setConfig({ auth0_domain: domain, auth0_client_id: clientId, auth0_audience: audience || "" });
        } else {
          setConfigError(true);
        }
      });
  }, []);

  if (configError) {
    return (
      <div className="min-h-screen bg-base flex items-center justify-center">
        <p className="font-mono text-xs text-text-muted">SYSTEM OFFLINE — CONFIG UNAVAILABLE</p>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="min-h-screen bg-base flex items-center justify-center">
        <span className="font-mono text-xs text-amber-tac animate-pulse_amber tracking-widest">
          INITIALISING...
        </span>
      </div>
    );
  }

  return (
    <Auth0Provider
      domain={config.auth0_domain}
      clientId={config.auth0_client_id}
      authorizationParams={{
        redirect_uri: window.location.origin + "/callback",
        audience: config.auth0_audience || undefined,
      }}
    >
      <BrowserRouter>
        <EngagementProvider>
        <PrefetchOnAuth />
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/callback" element={<Callback />} />
          <Route path="/deck" element={<Navigate to="/deck/missions" replace />} />
          <Route path="/deck/missions" element={<MissionDeck />} />
          <Route path="/deck/intel" element={<IntelDeck />} />
          <Route path="/deck/pilots" element={<Pilots />} />
          <Route path="/deck/connections" element={<Navigate to="/deck/settings" replace />} />
          <Route path="/deck/settings" element={<Connections />} />
          <Route path="/deck/sortie" element={<Sortie />} />
          <Route path="/deck/logbook" element={<Logbook />} />
          <Route path="/dashboard" element={<Navigate to="/deck/missions" replace />} />
          <Route path="/missions/:missionId" element={<Mission />} />
        </Routes>
        </EngagementProvider>
      </BrowserRouter>
    </Auth0Provider>
  );
}
