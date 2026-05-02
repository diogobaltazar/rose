import type { Session, Agent } from '../sdk/types';
import { COLORS, HIGHLIGHT_TTL, fmtSize, fmtDuration, fmtTokens, fmtUsd } from './constants';

const _prevMetrics: Record<string, number> = {};
const _highlightUntil: Record<string, number> = {};

function checkDelta(key: string, value: number | null): boolean {
  if (value == null) return false;
  const now = Date.now();
  const prev = _prevMetrics[key];
  _prevMetrics[key] = value;
  if (prev != null && value > prev) {
    _highlightUntil[key] = now + HIGHLIGHT_TTL;
  }
  return now < (_highlightUntil[key] || 0);
}

interface MetricCellProps {
  value: number | null;
  formatted: string;
  deltaKey?: string;
  color: string;
}

function MetricCell({ value, formatted, deltaKey, color }: MetricCellProps) {
  const highlighted = deltaKey && value != null && checkDelta(deltaKey, value);
  return (
    <td className="matrix-cell" style={{ color: highlighted ? COLORS.delta : color }}>
      {formatted}
      {highlighted && <span className="delta-arrow"> ↑</span>}
    </td>
  );
}

interface Props {
  session: Session;
}

interface AgentRow {
  agentType: string;
  agentId: string;
  status: 'live' | 'done';
  invocations: number;
  totalKb: number;
  totalTools: number;
  totalTokens: number;
  totalUsd: number;
  duration: number;
}

export function AgentMatrix({ session }: Props) {
  const agents = session.agents || [];
  if (agents.length === 0) return null;

  const sid = session.session_id;

  const groups: Record<string, Agent[]> = {};
  for (const a of agents) {
    if (!groups[a.agent_type]) groups[a.agent_type] = [];
    groups[a.agent_type].push(a);
  }

  const agentRows: AgentRow[] = Object.entries(groups).map(([agentType, invocations]) => {
    const last = invocations[invocations.length - 1];
    const rowLive = invocations.some(a => a.status === 'live');
    return {
      agentType,
      agentId: last.agent_id,
      status: rowLive ? 'live' : 'done',
      invocations: invocations.length,
      totalKb: Math.round(invocations.reduce((s, a) => s + (a.size_kb || 0), 0) * 10) / 10,
      totalTools: invocations.reduce((s, a) => s + a.tool_count, 0),
      totalTokens: invocations.reduce((s, a) => s + a.tokens, 0),
      totalUsd: invocations.reduce((s, a) => s + a.usd, 0),
      duration: invocations.reduce((s, a) => s + (a.duration || 0), 0),
    };
  });

  const sumKb = Math.round((agentRows.reduce((s, r) => s + r.totalKb, 0) + (session.own_kb || 0)) * 10) / 10;
  const sumTools = agentRows.reduce((s, r) => s + r.totalTools, 0) + (session.own_tools || 0);
  const sumDur = agentRows.reduce((s, r) => s + r.duration, 0) + (session.own_duration || 0);
  const sumTokens = agentRows.reduce((s, r) => s + r.totalTokens, 0) + (session.own_tokens || 0);
  const sumUsd = agentRows.reduce((s, r) => s + r.totalUsd, 0) + (session.own_usd || 0);
  const sumInv = agentRows.reduce((s, r) => s + r.invocations, 0) + 1;

  const titleLower = (session.title || '').trim().toLowerCase();
  const mainName = titleLower.startsWith('/topgun') ? 'topgun' : 'claude';
  const mainSid = sid.replace(/-/g, '').slice(0, 17);

  return (
    <div className="matrix-container">
      <table className="matrix-table">
        <thead>
          <tr>
            <th></th>
            <th style={{ color: COLORS.silver }}>memory</th>
            <th style={{ color: COLORS.silver }}>tools</th>
            <th style={{ color: COLORS.silver }}>time</th>
            <th style={{ color: COLORS.silver }}>tokens</th>
            <th style={{ color: COLORS.silver }}>USD</th>
            <th style={{ color: COLORS.silver }}>×</th>
          </tr>
        </thead>
        <tbody>
          <tr className="matrix-summary-row">
            <td></td>
            <td className="matrix-cell" style={{ color: COLORS.mem, fontWeight: 600 }}>{fmtSize(sumKb)}</td>
            <td className="matrix-cell" style={{ color: COLORS.tool, fontWeight: 600 }}>{sumTools}</td>
            <td className="matrix-cell" style={{ color: COLORS.time, fontWeight: 600 }}>{fmtDuration(sumDur)}</td>
            <td className="matrix-cell" style={{ color: COLORS.tok, fontWeight: 600 }}>{fmtTokens(sumTokens)}</td>
            <td className="matrix-cell" style={{ color: COLORS.usd, fontWeight: 600 }}>{fmtUsd(sumUsd)}</td>
            <td className="matrix-cell" style={{ color: COLORS.dim, fontWeight: 600 }}>×{sumInv}</td>
          </tr>
          <tr className="matrix-rule"><td colSpan={7}><div className="matrix-rule-line"></div></td></tr>
          {agentRows.map(r => {
            const k = `${sid}:${r.agentType}:`;
            return (
              <tr key={r.agentType}>
                <td className="matrix-label">
                  <span className={`status-dot ${r.status === 'live' ? 'live' : ''}`}>
                    {r.status === 'live' ? '●' : '○'}
                  </span>
                  <span className="agent-id">{r.agentId}</span>
                  <span className="agent-type">{r.agentType}</span>
                </td>
                <MetricCell value={r.totalKb} formatted={fmtSize(r.totalKb)} deltaKey={k+'kb'} color={COLORS.mem} />
                <MetricCell value={r.totalTools} formatted={String(r.totalTools)} deltaKey={k+'tools'} color={COLORS.tool} />
                <MetricCell value={r.duration} formatted={fmtDuration(r.duration)} deltaKey={k+'dur'} color={COLORS.time} />
                <MetricCell value={r.totalTokens} formatted={fmtTokens(r.totalTokens)} deltaKey={k+'tok'} color={COLORS.tok} />
                <MetricCell value={r.totalUsd} formatted={fmtUsd(r.totalUsd)} deltaKey={k+'usd'} color={COLORS.usd} />
                <MetricCell value={r.invocations} formatted={`×${r.invocations}`} deltaKey={k+'inv'} color={COLORS.dim} />
              </tr>
            );
          })}
          <tr>
            <td className="matrix-label">
              <span className={`status-dot ${session.status === 'live' ? 'live' : ''}`}>
                {session.status === 'live' ? '●' : '○'}
              </span>
              <span className="agent-id">{mainSid}</span>
              <span className="agent-type">{mainName}</span>
            </td>
            <MetricCell value={session.own_kb} formatted={fmtSize(session.own_kb)} deltaKey={`${sid}:main:kb`} color={COLORS.mem} />
            <MetricCell value={session.own_tools} formatted={String(session.own_tools || 0)} deltaKey={`${sid}:main:tools`} color={COLORS.tool} />
            <MetricCell value={session.own_duration} formatted={fmtDuration(session.own_duration)} deltaKey={`${sid}:main:dur`} color={COLORS.time} />
            <MetricCell value={session.own_tokens} formatted={fmtTokens(session.own_tokens)} deltaKey={`${sid}:main:tok`} color={COLORS.tok} />
            <MetricCell value={session.own_usd} formatted={fmtUsd(session.own_usd)} deltaKey={`${sid}:main:usd`} color={COLORS.usd} />
            <td className="matrix-cell" style={{ color: COLORS.dim }}>×1</td>
          </tr>
        </tbody>
      </table>
    </div>
  );
}
