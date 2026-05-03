import { useState } from "react";
import type { Engagement } from "../types";
import StatusPip from "./StatusPip";

interface Props {
  engagement: Engagement;
}

function fmtDuration(s: number | null): string {
  if (s === null) return "—";
  if (s < 60) return `${Math.round(s)}s`;
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60);
  return `${m}m ${sec}s`;
}

function fmtTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`;
  return String(n);
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("en-GB", {
    month: "short", day: "numeric", hour: "2-digit", minute: "2-digit",
  });
}

export default function EngagementRow({ engagement: e }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="tac-border bg-card hover:bg-card-hover transition-colors">
      <button
        className="w-full text-left p-4 flex items-center gap-4 group"
        onClick={() => setExpanded((v) => !v)}
      >
        <StatusPip status={e.status} />

        <span className="font-mono text-xs text-text-secondary group-hover:text-amber-tac transition-colors truncate flex-1 min-w-0">
          {e.branch ?? e.session_id.slice(0, 16)}
        </span>

        <div className="flex items-center gap-6 shrink-0">
          <div className="hidden sm:block text-right">
            <div className="telemetry-label">STARTED</div>
            <div className="telemetry-value text-xs">{fmtDate(e.started_at)}</div>
          </div>
          <div className="text-right">
            <div className="telemetry-label">ELAPSED</div>
            <div className="telemetry-value text-xs">{fmtDuration(e.duration)}</div>
          </div>
          <div className="text-right">
            <div className="telemetry-label">TOKENS</div>
            <div className="telemetry-value text-xs">{fmtTokens(e.total_tokens)}</div>
          </div>
          <div className="text-right">
            <div className="telemetry-label">COST</div>
            <div className="telemetry-value text-xs">${e.total_usd.toFixed(2)}</div>
          </div>
          <div className="text-right">
            <div className="telemetry-label">TOOLS</div>
            <div className="telemetry-value text-xs">{e.total_tools}</div>
          </div>
          <span className="font-mono text-text-muted text-xs">{expanded ? "▲" : "▼"}</span>
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-border-dim pt-3 space-y-3 animate-fadeIn">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            <div>
              <div className="telemetry-label mb-0.5">SESSION ID</div>
              <div className="font-mono text-xs text-text-secondary truncate">{e.session_id}</div>
            </div>
            <div>
              <div className="telemetry-label mb-0.5">PROJECT</div>
              <div className="font-mono text-xs text-text-secondary truncate">{e.project.split("/").pop() ?? e.project}</div>
            </div>
          </div>

          {e.agents.length > 0 && (
            <div>
              <div className="telemetry-label mb-2">AGENTS ({e.agents.length})</div>
              <div className="space-y-1.5">
                {e.agents.map((a) => (
                  <div key={a.agent_id} className="flex items-center gap-3 text-xs font-mono bg-base/60 px-3 py-2 border border-border-dim">
                    <StatusPip status={a.status} />
                    <span className="text-text-secondary truncate flex-1">{a.agent_type}</span>
                    {a.description && (
                      <span className="text-text-muted truncate max-w-[200px]">{a.description}</span>
                    )}
                    <span className="text-text-muted shrink-0">{fmtDuration(a.duration)}</span>
                    <span className="text-text-muted shrink-0">{a.tool_count} tools</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
