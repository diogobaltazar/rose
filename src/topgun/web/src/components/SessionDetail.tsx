import type { Session } from '../sdk/types';
import { COLORS, fmtDt } from './constants';
import { AgentMatrix } from './AgentMatrix';

interface Props {
  session: Session | null;
}

function sessionTitle(s: Session): string {
  if (s.title) {
    const t = s.title.trim();
    return t.length > 74 ? t.slice(0, 71) + '…' : t;
  }
  const b = s.branch || '';
  if (b && b !== 'main' && b !== 'master') return b;
  return s.session_id?.slice(0, 12) || 'session';
}

function HeaderRow({ label, value, valueClass }: { label: string; value: string; valueClass?: string }) {
  return (
    <div className="header-row">
      <span className="header-key">{label}</span>
      <span className={`header-val ${valueClass || ''}`}>{value}</span>
    </div>
  );
}

export function SessionDetail({ session }: Props) {
  if (!session) return <div className="placeholder">select a session</div>;

  const meta = session.meta || {};
  const issues = meta.issues as string | string[] | undefined;
  const tag = meta.tag as string | undefined;
  const pr = meta.pr as string | undefined;
  const chain = session.process_sid && session.process_sid !== session.session_id
    ? `${session.session_id}  ←  ${session.process_sid}`
    : session.session_id;

  return (
    <div className="session-detail">
      {(session.title || meta.feature) ? (
        <div className="detail-title">
          {sessionTitle({ ...session, title: session.title || String(meta.feature || '') })}
        </div>
      ) : null}

      <div className="detail-header">
        <HeaderRow label="session" value={chain} valueClass="val-neon" />
        <HeaderRow label="created" value={fmtDt(session.started_at)} valueClass="val-dim" />
        {session.project && <HeaderRow label="tree" value={session.project} valueClass="val-neon-dim" />}
        {session.branch && <HeaderRow label="branch" value={session.branch} valueClass="val-neon-dim" />}
        <HeaderRow
          label="issue(s)"
          value={issues ? (Array.isArray(issues) ? issues.join('  ') : String(issues)) : 'undefined'}
          valueClass={issues ? 'val-default' : 'val-undef'}
        />
        <HeaderRow label="tag" value={tag || 'undefined'} valueClass={tag ? 'val-default' : 'val-undef'} />
        <HeaderRow label="PR" value={pr || 'undefined'} valueClass={pr ? 'val-default' : 'val-undef'} />
      </div>

      <AgentMatrix session={session} />

      {(!session.agents || session.agents.length === 0) && (
        <div className="detail-rule"></div>
      )}
    </div>
  );
}
