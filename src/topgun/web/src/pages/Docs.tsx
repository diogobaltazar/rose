import { useState, useEffect } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import NavBar from "../components/NavBar";
import HUDGrid from "../components/HUDGrid";
import { fetchDocs } from "../api";

// ── Minimal markdown renderer ─────────────────────────────────────────────────

function renderMarkdown(md: string): React.ReactNode[] {
  const lines = md.split("\n");
  const nodes: React.ReactNode[] = [];
  let i = 0;
  let key = 0;

  while (i < lines.length) {
    const line = lines[i];

    // Code block
    if (line.startsWith("```")) {
      const lang = line.slice(3).trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i].startsWith("```")) {
        codeLines.push(lines[i]);
        i++;
      }
      nodes.push(
        <div key={key++} className="my-4">
          {lang && (
            <div className="font-mono text-xs text-text-muted tracking-widest px-3 py-1 border-t border-l border-r border-border-dim bg-card/50">
              {lang}
            </div>
          )}
          <pre className="font-mono text-xs text-green-live bg-card border border-border-dim px-4 py-3 overflow-x-auto whitespace-pre">
            {codeLines.join("\n")}
          </pre>
        </div>
      );
      i++;
      continue;
    }

    // Blockquote
    if (line.startsWith("> ")) {
      const text = line.slice(2);
      nodes.push(
        <div key={key++} className="border-l-2 border-amber-tac/40 pl-4 my-2">
          <p className="font-mono text-xs text-text-muted italic">{text}</p>
        </div>
      );
      i++;
      continue;
    }

    // H1
    if (line.startsWith("# ")) {
      nodes.push(
        <h1 key={key++} className="font-mono text-base font-bold text-text-primary mt-8 mb-3 tracking-wide">
          {line.slice(2)}
        </h1>
      );
      i++;
      continue;
    }

    // H2
    if (line.startsWith("## ")) {
      nodes.push(
        <h2 key={key++} className="font-mono text-sm font-semibold text-amber-tac mt-6 mb-2 tracking-widest uppercase">
          {line.slice(3)}
        </h2>
      );
      i++;
      continue;
    }

    // H3
    if (line.startsWith("### ")) {
      nodes.push(
        <h3 key={key++} className="font-mono text-xs font-semibold text-text-primary mt-4 mb-1 tracking-widest">
          {line.slice(4)}
        </h3>
      );
      i++;
      continue;
    }

    // Table (starts with |)
    if (line.startsWith("|")) {
      const rows: string[][] = [];
      while (i < lines.length && lines[i].startsWith("|")) {
        if (!lines[i].match(/^\|[-| ]+\|$/)) {
          rows.push(lines[i].split("|").slice(1, -1).map(c => c.trim()));
        }
        i++;
      }
      nodes.push(
        <div key={key++} className="my-4 overflow-x-auto">
          <table className="font-mono text-xs w-full border-collapse">
            {rows.map((row, ri) => (
              <tr key={ri} className={ri === 0 ? "border-b border-amber-tac/40" : "border-b border-border-dim"}>
                {row.map((cell, ci) => (
                  <td key={ci} className={`px-4 py-1.5 ${ri === 0 ? "text-amber-tac tracking-widest" : "text-text-primary"}`}>
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </table>
        </div>
      );
      continue;
    }

    // List item
    if (line.match(/^[-*] /)) {
      nodes.push(
        <div key={key++} className="flex gap-3 my-0.5">
          <span className="font-mono text-xs text-amber-tac/60 shrink-0">·</span>
          <span className="font-mono text-xs text-text-primary">{inlineFormat(line.slice(2))}</span>
        </div>
      );
      i++;
      continue;
    }

    // Numbered list
    const numMatch = line.match(/^(\d+)\. (.+)/);
    if (numMatch) {
      nodes.push(
        <div key={key++} className="flex gap-3 my-0.5">
          <span className="font-mono text-xs text-amber-tac/60 shrink-0 w-4">{numMatch[1]}.</span>
          <span className="font-mono text-xs text-text-primary">{inlineFormat(numMatch[2])}</span>
        </div>
      );
      i++;
      continue;
    }

    // Blank line
    if (line.trim() === "") {
      nodes.push(<div key={key++} className="h-2" />);
      i++;
      continue;
    }

    // Paragraph
    nodes.push(
      <p key={key++} className="font-mono text-xs text-text-primary leading-relaxed">
        {inlineFormat(line)}
      </p>
    );
    i++;
  }

  return nodes;
}

function inlineFormat(text: string): React.ReactNode {
  // Bold **text** and inline `code`
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g);
  return parts.map((part, i) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={i} className="font-mono text-xs text-green-live bg-card px-1 border border-border-dim">{part.slice(1, -1)}</code>;
    }
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i} className="text-text-primary font-semibold">{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}

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
