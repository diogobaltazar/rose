import { Link } from "react-router-dom";
import type { Mission } from "../types";
import StatusPip from "./StatusPip";

interface Props {
  mission: Mission;
  engagementCount?: number;
}

const priorityBadge: Record<string, string> = {
  high:   "text-red-alert border-red-alert/40",
  medium: "text-amber-tac border-amber-tac/40",
  low:    "text-text-secondary border-text-muted/30",
};

export default function MissionCard({ mission, engagementCount }: Props) {
  const id = encodeURIComponent(mission.id);

  return (
    <Link
      to={`/missions/${id}`}
      className="block tac-card p-5 hover:bg-card-hover hover:border-border-bright transition-all duration-200 group bracket-corners"
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 min-w-0">
          {mission.number && (
            <span className="font-mono text-xs text-text-muted shrink-0">#{mission.number}</span>
          )}
          <h3 className="font-mono text-sm text-text-primary truncate group-hover:text-amber-tac transition-colors">
            {mission.title}
          </h3>
        </div>
        <StatusPip status={mission.state} />
      </div>

      {mission.about && (
        <p className="text-xs text-text-secondary leading-relaxed mb-3 line-clamp-2">
          {mission.about}
        </p>
      )}

      <div className="flex items-center gap-4 mt-auto">
        {mission.priority && (
          <span className={`font-mono text-xs border px-2 py-0.5 ${priorityBadge[mission.priority] ?? priorityBadge.low}`}>
            {mission.priority.toUpperCase()}
          </span>
        )}
        {engagementCount !== undefined && (
          <span className="font-mono text-xs text-text-muted ml-auto">
            {engagementCount} {engagementCount === 1 ? "engagement" : "engagements"}
          </span>
        )}
        {mission.source_type === "github" && (
          <span className="font-mono text-xs text-text-muted">GH</span>
        )}
        {mission.source_type === "obsidian" && (
          <span className="font-mono text-xs text-text-muted">OBS</span>
        )}
      </div>
    </Link>
  );
}
