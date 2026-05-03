import { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { useAuth0 } from "@auth0/auth0-react";
import { getMissions, getEngagements } from "../api";
import type { Mission as MissionType, Engagement } from "../types";
import NavBar from "../components/NavBar";
import StatusPip from "../components/StatusPip";
import EngagementRow from "../components/EngagementRow";
import HUDGrid from "../components/HUDGrid";

export default function Mission() {
  const { missionId } = useParams<{ missionId: string }>();
  const { isAuthenticated, getAccessTokenSilently } = useAuth0();
  const [mission, setMission] = useState<MissionType | null>(null);
  const [engagements, setEngagements] = useState<Engagement[]>([]);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);

  const decoded = missionId ? decodeURIComponent(missionId) : "";

  useEffect(() => {
    if (!isAuthenticated || !decoded) return;
    (async () => {
      try {
        let token = "";
        try { token = await getAccessTokenSilently(); } catch { /* dev */ }
        const [allMissions, engs] = await Promise.all([
          getMissions(token),
          getEngagements(decoded, token),
        ]);
        setMission(allMissions.find((m) => m.id === decoded) ?? null);
        setEngagements(engs);
      } finally {
        setLoading(false);
      }
    })();
  }, [isAuthenticated, decoded, getAccessTokenSilently]);

  function copyCommand() {
    const cmd = `topgun engage --mission "${decoded}"`;
    navigator.clipboard.writeText(cmd).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-base flex items-center justify-center">
        <span className="font-mono text-xs text-amber-tac animate-pulse_amber tracking-widest">
          LOADING MISSION...
        </span>
      </div>
    );
  }

  if (!mission) {
    return (
      <div className="min-h-screen bg-base flex items-center justify-center">
        <div className="tac-border p-8 text-center bracket-corners">
          <p className="font-mono text-xs text-red-alert tracking-widest">MISSION NOT FOUND</p>
          <Link to="/dashboard" className="font-mono text-xs text-text-muted hover:text-amber-tac mt-3 block">
            ← Return to dashboard
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-base text-text-primary">
      <HUDGrid />
      <NavBar />

      <main className="relative z-10 max-w-4xl mx-auto px-6 py-10">
        {/* Breadcrumb */}
        <div className="font-mono text-xs text-text-muted mb-6 tracking-widest">
          <Link to="/dashboard" className="hover:text-amber-tac transition-colors">MISSIONS</Link>
          <span className="mx-2 text-border-bright">›</span>
          <span className="text-text-secondary">
            {mission.number ? `#${mission.number}` : mission.id}
          </span>
        </div>

        {/* Mission briefing */}
        <div className="tac-border p-6 mb-8 bracket-corners">
          <div className="flex items-start justify-between gap-4 mb-4">
            <div className="flex-1 min-w-0">
              <div className="font-mono text-xs text-amber-tac tracking-widest mb-1">
                MISSION BRIEF
              </div>
              <h1 className="font-mono text-lg font-semibold text-text-primary">
                {mission.title}
              </h1>
            </div>
            <div className="flex items-center gap-3 shrink-0">
              <StatusPip status={mission.state} />
              {mission.url && (
                <a
                  href={mission.url}
                  target="_blank"
                  rel="noreferrer"
                  className="font-mono text-xs text-text-muted hover:text-amber-tac transition-colors"
                >
                  GH ↗
                </a>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 border-t border-border-dim pt-4 mb-4">
            <div>
              <div className="telemetry-label mb-0.5">SOURCE</div>
              <div className="telemetry-value">{mission.source_type.toUpperCase()}</div>
            </div>
            {mission.number && (
              <div>
                <div className="telemetry-label mb-0.5">ISSUE</div>
                <div className="telemetry-value">#{mission.number}</div>
              </div>
            )}
            {mission.priority && (
              <div>
                <div className="telemetry-label mb-0.5">PRIORITY</div>
                <div className="telemetry-value text-amber-tac">{mission.priority.toUpperCase()}</div>
              </div>
            )}
            <div>
              <div className="telemetry-label mb-0.5">ENGAGEMENTS</div>
              <div className="telemetry-value">{engagements.length}</div>
            </div>
          </div>

          {mission.about && (
            <div className="mb-3">
              <div className="telemetry-label mb-1.5">OBJECTIVE</div>
              <p className="text-sm text-text-secondary leading-relaxed">{mission.about}</p>
            </div>
          )}

          {mission.motivation && (
            <div className="mb-3">
              <div className="telemetry-label mb-1.5">MOTIVATION</div>
              <p className="text-sm text-text-secondary leading-relaxed">{mission.motivation}</p>
            </div>
          )}

          {mission.acceptance_criteria.length > 0 && (
            <div>
              <div className="telemetry-label mb-2">ACCEPTANCE CRITERIA</div>
              <ul className="space-y-1.5">
                {mission.acceptance_criteria.map((ac, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-text-secondary">
                    <span className="text-amber-tac mt-0.5 shrink-0">◈</span>
                    <span>{ac}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* Engage CTA */}
        <div className="tac-border bg-card p-5 mb-8 flex items-center justify-between gap-4">
          <div>
            <div className="font-mono text-xs text-amber-tac tracking-widest mb-1">LAUNCH NEW ENGAGEMENT</div>
            <code className="font-mono text-xs text-text-secondary">
              topgun engage --mission &quot;{decoded}&quot;
            </code>
          </div>
          <button
            onClick={copyCommand}
            className="btn-amber shrink-0"
          >
            {copied ? "COPIED ✓" : "COPY CMD"}
          </button>
        </div>

        {/* Engagements */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <div className="font-mono text-xs text-amber-tac tracking-widest uppercase">
              Engagement History
            </div>
            <div className="font-mono text-xs text-text-muted">
              {engagements.filter((e) => e.status === "live").length} live
            </div>
          </div>

          {engagements.length === 0 ? (
            <div className="tac-border p-10 text-center bracket-corners">
              <p className="font-mono text-xs text-text-muted tracking-widest">NO ENGAGEMENTS YET</p>
              <p className="font-mono text-xs text-text-muted/60 mt-2">
                Run the command above to launch the first engagement.
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {engagements.map((e) => (
                <EngagementRow key={e.session_id} engagement={e} />
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
