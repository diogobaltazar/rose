import { useState, useEffect } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import NavBar from "../components/NavBar";
import HUDGrid from "../components/HUDGrid";
import { fetchDocs } from "../api";

import { renderMarkdown } from "../utils/markdown";

// ── Doc entries ───────────────────────────────────────────────────────────────

interface DocEntry { slug: string; title: string; description: string; }

const USER_DOCS: DocEntry[] = [
  // Placeholder — user docs will be added here as markdown files
];

const DEV_DOCS: DocEntry[] = [
  {
    slug: "google-drive-oauth",
    title: "Google Drive OAuth2 Setup",
    description: "Create a GCP OAuth2 app and connect it to topgun for Google Drive storage.",
  },
  {
    slug: "ARCHITECTURE",
    title: "Architecture",
    description: "Full system design, data flow, and deployment overview.",
  },
  {
    slug: "auth0-setup",
    title: "Auth0 Setup",
    description: "Configure Auth0 applications for the webapp and CLI.",
  },
];

// ── Page ──────────────────────────────────────────────────────────────────────

type Tab = "user" | "dev";

export default function Docs() {
  const { isLoading, isAuthenticated, loginWithRedirect } = useAuth0();
  const [tab, setTab] = useState<Tab>("dev");
  const [openSlug, setOpenSlug] = useState<string | null>(null);
  const [docContent, setDocContent] = useState<string | null>(null);
  const [docLoading, setDocLoading] = useState(false);
  const [docError, setDocError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoading && !isAuthenticated) loginWithRedirect();
  }, [isAuthenticated, isLoading, loginWithRedirect]);

  const openDoc = async (slug: string) => {
    setOpenSlug(slug);
    setDocContent(null);
    setDocError(null);
    setDocLoading(true);
    try {
      setDocContent(await fetchDocs(slug));
    } catch (e) {
      setDocError(String(e));
    } finally {
      setDocLoading(false);
    }
  };

  const docs = tab === "user" ? USER_DOCS : DEV_DOCS;

  if (isLoading) {
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
      <main className="relative z-10 max-w-5xl mx-auto px-6 py-10 flex gap-6" style={{ minHeight: "calc(100vh - 56px)" }}>

        {/* Sidebar */}
        <aside className="w-64 shrink-0">
          <div className="font-mono text-xs text-amber-tac tracking-[0.4em] uppercase mb-1">Documentation</div>
          <h1 className="font-mono text-xl font-semibold mb-6">Docs</h1>

          {/* Tabs */}
          <div className="flex mb-4 border-b border-border-dim">
            {(["user", "dev"] as Tab[]).map(t => (
              <button key={t} onClick={() => { setTab(t); setOpenSlug(null); }}
                className={`font-mono text-xs px-4 py-1.5 tracking-widest ${
                  tab === t ? "text-amber-tac border-b border-amber-tac -mb-px" : "text-text-muted hover:text-text-secondary"
                }`}>
                {t === "user" ? "USER" : "DEVELOPER"}
              </button>
            ))}
          </div>

          {/* Doc list */}
          <div className="space-y-1">
            {docs.length === 0 ? (
              <p className="font-mono text-xs text-text-muted">No docs yet.</p>
            ) : docs.map(d => (
              <button key={d.slug} onClick={() => openDoc(d.slug)}
                className={`w-full text-left px-3 py-2 border transition-colors ${
                  openSlug === d.slug
                    ? "border-amber-tac/60 bg-amber-tac/5 text-amber-tac"
                    : "border-transparent text-text-muted hover:text-text-primary hover:border-border-dim"
                }`}>
                <div className="font-mono text-xs">{d.title}</div>
                <div className="font-mono text-xs text-text-muted mt-0.5 leading-relaxed">{d.description}</div>
              </button>
            ))}
          </div>
        </aside>

        {/* Content */}
        <article className="flex-1 min-w-0">
          {!openSlug ? (
            <div className="flex items-center justify-center h-64">
              <p className="font-mono text-xs text-text-muted tracking-widest">SELECT A DOCUMENT</p>
            </div>
          ) : docLoading ? (
            <div className="flex items-center gap-3 pt-8">
              <span className="font-mono text-xs text-amber-tac animate-pulse_amber tracking-widest">LOADING…</span>
            </div>
          ) : docError ? (
            <div className="tac-border p-4">
              <p className="font-mono text-xs text-red-alert">{docError}</p>
            </div>
          ) : docContent ? (
            <div className="tac-border p-6">
              {renderMarkdown(docContent)}
            </div>
          ) : null}
        </article>
      </main>
    </div>
  );
}
