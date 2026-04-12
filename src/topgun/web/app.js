const { useState, useEffect, useRef, useMemo, useCallback } = React;

// ─── Constants ─────────────────────────────────────────────────────────────

const WS_BASE = `ws://${window.location.hostname}:${window.location.port || 8000}`;

// CLI colour palette (xterm-256 approximations)
const COLORS = {
  neon:     '#87d787',  // color(118) — live dot, session ID
  neonDim:  '#005f00',  // color(28)  — branch, agent type
  pearl:    '#dadada',  // color(253) — feature one-liner
  silver:   '#8a8a8a',  // color(245) — labels, keys
  dim:      '#6c6c6c',  // dim grey
  val:      '#dadada',  // color(253) — values
  delta:    '#00afff',  // color(39)  — value-increased highlight
  mem:      '#87afaf',  // color(109) — memory
  tool:     '#d7af87',  // color(180) — tools
  time:     '#afafaf',  // color(145) — time
  tok:      '#87af87',  // color(114) — tokens
  usd:      '#ffaf87',  // color(216) — USD
};

const HIGHLIGHT_TTL = 2000; // ms — how long delta highlights stay lit

// ─── Formatting helpers (matching CLI) ─────────────────────────────────────

function fmtDt(iso) {
  if (!iso) return '—';
  try {
    const dt = new Date(iso);
    const day = String(dt.getDate()).padStart(2, '0');
    const mon = dt.toLocaleString('en-GB', { month: 'short' }).toUpperCase();
    const year = dt.getFullYear();
    const time = dt.toLocaleTimeString('en-GB', { hour12: false });
    return `${day}-${mon}-${year} ${time}`;
  } catch { return iso.slice(0, 19); }
}

function fmtSize(kb) {
  if (kb == null) return '—';
  if (kb >= 1024) return `${(kb / 1024).toFixed(1)} MB`;
  return `${kb.toFixed(1)} KB`;
}

function fmtDuration(seconds) {
  if (seconds == null || seconds < 0) return '—';
  const totalM = seconds / 60;
  if (totalM < 1) return `${Math.floor(seconds)}s`;
  const totalH = totalM / 60;
  if (totalH < 1) return `${Math.floor(totalM)}m`;
  const totalD = totalH / 24;
  if (totalD < 1) return `${totalH.toFixed(1)}h`;
  return `${totalD.toFixed(1)}d`;
}

function fmtTokens(n) {
  if (n == null) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function fmtUsd(usd) {
  if (usd == null) return '—';
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(3)}`;
}

function sessionTitle(s) {
  if (s.title) {
    const t = s.title.trim();
    return t.length > 74 ? t.slice(0, 71) + '…' : t;
  }
  const b = s.branch || '';
  if (b && b !== 'main' && b !== 'master') return b;
  return s.session_id?.slice(0, 12) || 'session';
}

function projectName(s) {
  const project = s.project || '';
  if (!project) return s.session_id?.slice(0, 8) || '?';
  const parts = project.split('/');
  return parts[parts.length - 1] || project;
}

// ─── Delta highlight tracker ───────────────────────────────────────────────

const _prevMetrics = {};
const _highlightUntil = {};

function checkDelta(key, value) {
  const now = Date.now();
  const prev = _prevMetrics[key];
  _prevMetrics[key] = value;
  if (prev != null && value > prev) {
    _highlightUntil[key] = now + HIGHLIGHT_TTL;
  }
  return now < (_highlightUntil[key] || 0);
}

// ─── Agent Matrix Table ────────────────────────────────────────────────────

function MetricCell({ value, formatted, deltaKey, color }) {
  const highlighted = deltaKey && value != null && checkDelta(deltaKey, value);
  return (
    <td className="matrix-cell" style={{ color: highlighted ? COLORS.delta : color }}>
      {formatted}
      {highlighted && <span className="delta-arrow"> ↑</span>}
    </td>
  );
}

function AgentMatrix({ session }) {
  const agents = session.agents || [];
  if (agents.length === 0) return null;

  const sid = session.session_id;

  // Group agents by type
  const groups = {};
  for (const a of agents) {
    if (!groups[a.agent_type]) groups[a.agent_type] = [];
    groups[a.agent_type].push(a);
  }

  const agentRows = Object.entries(groups).map(([agentType, invocations]) => {
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

  // Summary totals (agents + main session)
  const sumKb = Math.round((agentRows.reduce((s, r) => s + r.totalKb, 0) + (session.own_kb || 0)) * 10) / 10;
  const sumTools = agentRows.reduce((s, r) => s + r.totalTools, 0) + (session.own_tools || 0);
  const sumDur = agentRows.reduce((s, r) => s + r.duration, 0) + (session.own_duration || 0);
  const sumTokens = agentRows.reduce((s, r) => s + r.totalTokens, 0) + (session.own_tokens || 0);
  const sumUsd = agentRows.reduce((s, r) => s + r.totalUsd, 0) + (session.own_usd || 0);
  const sumInv = agentRows.reduce((s, r) => s + r.invocations, 0) + 1;

  // Main session row label
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
          {/* Summary row */}
          <tr className="matrix-summary-row">
            <td></td>
            <td className="matrix-cell" style={{ color: COLORS.mem, fontWeight: 600 }}>{fmtSize(sumKb)}</td>
            <td className="matrix-cell" style={{ color: COLORS.tool, fontWeight: 600 }}>{sumTools}</td>
            <td className="matrix-cell" style={{ color: COLORS.time, fontWeight: 600 }}>{fmtDuration(sumDur)}</td>
            <td className="matrix-cell" style={{ color: COLORS.tok, fontWeight: 600 }}>{fmtTokens(sumTokens)}</td>
            <td className="matrix-cell" style={{ color: COLORS.usd, fontWeight: 600 }}>{fmtUsd(sumUsd)}</td>
            <td className="matrix-cell" style={{ color: COLORS.dim, fontWeight: 600 }}>×{sumInv}</td>
          </tr>

          {/* Separator */}
          <tr className="matrix-rule"><td colSpan="7"><div className="matrix-rule-line"></div></td></tr>

          {/* Per-agent-type rows */}
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
                <MetricCell value={r.totalTools} formatted={r.totalTools} deltaKey={k+'tools'} color={COLORS.tool} />
                <MetricCell value={r.duration} formatted={fmtDuration(r.duration)} deltaKey={k+'dur'} color={COLORS.time} />
                <MetricCell value={r.totalTokens} formatted={fmtTokens(r.totalTokens)} deltaKey={k+'tok'} color={COLORS.tok} />
                <MetricCell value={r.totalUsd} formatted={fmtUsd(r.totalUsd)} deltaKey={k+'usd'} color={COLORS.usd} />
                <MetricCell value={r.invocations} formatted={`×${r.invocations}`} deltaKey={k+'inv'} color={COLORS.dim} />
              </tr>
            );
          })}

          {/* Main session row */}
          <tr>
            <td className="matrix-label">
              <span className={`status-dot ${session.status === 'live' ? 'live' : ''}`}>
                {session.status === 'live' ? '●' : '○'}
              </span>
              <span className="agent-id">{mainSid}</span>
              <span className="agent-type">{mainName}</span>
            </td>
            <MetricCell value={session.own_kb} formatted={fmtSize(session.own_kb)} deltaKey={`${sid}:main:kb`} color={COLORS.mem} />
            <MetricCell value={session.own_tools} formatted={session.own_tools || 0} deltaKey={`${sid}:main:tools`} color={COLORS.tool} />
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

// ─── Session Detail ────────────────────────────────────────────────────────

function SessionDetail({ session }) {
  if (!session) return <div className="placeholder">select a session</div>;

  const meta = session.meta || {};
  const issues = meta.issues;
  const tag = meta.tag;
  const pr = meta.pr;
  const chain = session.process_sid && session.process_sid !== session.session_id
    ? `${session.session_id}  ←  ${session.process_sid}`
    : session.session_id;

  return (
    <div className="session-detail">
      {/* Feature one-liner */}
      {(session.title || meta.feature) && (
        <div className="detail-title">
          {sessionTitle({ ...session, title: session.title || meta.feature })}
        </div>
      )}

      {/* Metadata header */}
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

      {/* Agent matrix */}
      <AgentMatrix session={session} />

      {/* Separator when no agents */}
      {(!session.agents || session.agents.length === 0) && (
        <div className="detail-rule"></div>
      )}
    </div>
  );
}

function HeaderRow({ label, value, valueClass }) {
  return (
    <div className="header-row">
      <span className="header-key">{label}</span>
      <span className={`header-val ${valueClass || ''}`}>{value}</span>
    </div>
  );
}

// ─── Sidebar ───────────────────────────────────────────────────────────────

function Sidebar({ sessions, selectedId, onSelect }) {
  const sorted = [...sessions].sort((a, b) => {
    const ta = a.started_at || '';
    const tb = b.started_at || '';
    return tb.localeCompare(ta);
  });

  return (
    <div id="sidebar">
      <div id="sidebar-header">topgun observe</div>
      {sorted.length === 0 && (
        <div className="sidebar-empty">no sessions</div>
      )}
      {sorted.map(s => (
        <div
          key={s.session_id}
          className={`session-row ${s.session_id === selectedId ? 'selected' : ''}`}
          onClick={() => onSelect(s.session_id)}
        >
          <div className={`session-row-dot ${s.status === 'live' ? 'live' : ''}`} />
          <div className="session-row-body">
            <div className="session-row-title">{projectName(s)}</div>
            <div className="session-row-sub">
              {s.status === 'live' ? 'live' : 'done'}
              {s.started_at ? `  ${fmtDt(s.started_at).split(' ')[1] || ''}` : ''}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── App ───────────────────────────────────────────────────────────────────

function App() {
  const [sessions, setSessions] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const sessionWsRef = useRef(null);

  // Connect to session list websocket
  useEffect(() => {
    function connect() {
      const ws = new WebSocket(`${WS_BASE}/ws`);
      sessionWsRef.current = ws;

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (Array.isArray(data)) {
            setSessions(data);
            setSelectedId(prev => {
              if (prev) return prev;
              const live = data.filter(s => s.status === 'live');
              live.sort((a, b) => (b.started_at || '').localeCompare(a.started_at || ''));
              return live[0]?.session_id || data[0]?.session_id || null;
            });
          }
        } catch {}
      };

      ws.onclose = () => {
        setTimeout(connect, 2000);
      };
    }
    connect();
    return () => sessionWsRef.current?.close();
  }, []);

  const selectedSession = useMemo(
    () => sessions.find(s => s.session_id === selectedId) || null,
    [sessions, selectedId]
  );

  return (
    <div id="layout">
      <Sidebar
        sessions={sessions}
        selectedId={selectedId}
        onSelect={setSelectedId}
      />
      <div id="main">
        <SessionDetail session={selectedSession} />
      </div>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
