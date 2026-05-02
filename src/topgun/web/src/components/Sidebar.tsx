import type { Session } from '../sdk/types';
import { fmtDt } from './constants';

interface Props {
  sessions: Session[];
  selectedId: string | null;
  onSelect: (id: string) => void;
  activeView: string;
  onViewChange: (view: string) => void;
}

function projectName(s: Session): string {
  const project = s.project || '';
  if (!project) return s.session_id?.slice(0, 8) || '?';
  const parts = project.split('/');
  return parts[parts.length - 1] || project;
}

export function Sidebar({ sessions, selectedId, onSelect, activeView, onViewChange }: Props) {
  const sorted = [...sessions].sort((a, b) => {
    const ta = a.started_at || '';
    const tb = b.started_at || '';
    return tb.localeCompare(ta);
  });

  return (
    <div id="sidebar">
      <div id="sidebar-header">topgun</div>

      <div
        className={`sidebar-nav-item${activeView === 'backlog' ? ' active' : ''}`}
        onClick={() => onViewChange('backlog')}
      >
        <span className="snav-icon">▦</span> backlog
      </div>
      <div
        className={`sidebar-nav-item${activeView === 'observe' ? ' active' : ''}`}
        onClick={() => onViewChange('observe')}
      >
        <span className="snav-icon">◈</span> observe
      </div>

      {activeView === 'observe' && (
        <>
          <div className="sidebar-section-sep" />
          {sorted.length === 0 && <div className="sidebar-empty">no sessions</div>}
          {sorted.map(s => (
            <div
              key={s.session_id}
              className={`session-row${s.session_id === selectedId ? ' selected' : ''}`}
              onClick={() => onSelect(s.session_id)}
            >
              <div className={`session-row-dot${s.status === 'live' ? ' live' : ''}`} />
              <div className="session-row-body">
                <div className="session-row-title">{projectName(s)}</div>
                <div className="session-row-sub">
                  {s.status === 'live' ? 'live' : 'done'}
                  {s.started_at ? `  ${fmtDt(s.started_at).split(' ')[1] || ''}` : ''}
                </div>
              </div>
            </div>
          ))}
        </>
      )}
    </div>
  );
}
