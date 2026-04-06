const { useState, useEffect, useRef, useMemo, useCallback } = React;

// ─── Constants ─────────────────────────────────────────────────────────────

const WS_BASE = `ws://${window.location.hostname}:${window.location.port || 8000}`;

const ACTORS = [
  { id: 'user',          label: 'USER',          color: '#00B4FF' },  // Jedi blue
  { id: 'rose',          label: 'ROSE',          color: '#CC00FF' },  // Mace Windu purple
  { id: 'rose-research', label: 'ROSE RESEARCH', color: '#00FF88' },  // Yoda green
  { id: 'rose-backlog',  label: 'ROSE BACKLOG',  color: '#FF2222' },  // Sith red
];

const ACTOR_MAP = Object.fromEntries(ACTORS.map(a => [a.id, a]));

function actorColor(id) {
  return (ACTOR_MAP[id] || { color: '#666' }).color;
}

// State machine nodes — each paired with its lightsaber colour
const NODES = [
  {
    id: 'FP', cx: 90, cy: 250, r: 40,
    color: '#00B4FF', stepColor: '#00B4FF',   // Jedi blue
    label: 'USER',
    desc: ['Prompt assistant with', 'behaviour specs and', 'product questions'],
    entry: true,
  },
  {
    id: 'AF', cx: 290, cy: 250, r: 30,
    color: '#CC00FF', stepColor: '#CC00FF',   // Mace Windu purple
    label: 'ROSE',
    desc: ['Reads codebase;', 'decides on research'],
  },
  {
    id: 'DR', cx: 510, cy: 140, r: 30,
    color: '#00FF88', stepColor: '#00FF88',   // Yoda green
    label: 'ROSE RESEARCH',
    desc: ['Deep research via', 'Gemini relay (conditional)'],
    conditional: true,
  },
  {
    id: 'BI', cx: 510, cy: 360, r: 30,
    color: '#FF2222', stepColor: '#FF2222',   // Sith red
    label: 'ROSE BACKLOG',
    desc: ['Inspect backlog issues'],
  },
  {
    id: 'CONV', cx: 700, cy: 250, r: 22,
    color: '#E8E8FF', stepColor: '#E8E8FF',   // silver-white
    label: '',
    desc: [],
    convergence: true,
  },
];

const NODE_MAP = Object.fromEntries(NODES.map(n => [n.id, n]));

// Edges: from → to, whether dashed, control points for cubic bezier
const EDGES = [
  // FP → AF
  { id: 'fp-af', from: 'FP', to: 'AF', dashed: false,
    d: 'M 130,250 C 175,250 225,250 260,250' },
  // AF → DR (dashed — conditional on codebase read)
  { id: 'af-dr', from: 'AF', to: 'DR', dashed: true,
    d: 'M 312,237 C 360,185 440,162 480,158' },
  // AF → BI
  { id: 'af-bi', from: 'AF', to: 'BI', dashed: false,
    d: 'M 312,263 C 360,315 440,338 480,342' },
  // DR → CONV (dashed)
  { id: 'dr-conv', from: 'DR', to: 'CONV', dashed: true,
    d: 'M 540,158 C 615,170 668,210 678,242' },
  // BI → CONV (dashed)
  { id: 'bi-conv', from: 'BI', to: 'CONV', dashed: true,
    d: 'M 540,342 C 615,330 668,290 678,258' },
];

// ─── Event parsing ──────────────────────────────────────────────────────────

function deriveNodeStates(events) {
  const active = new Set();
  const completed = new Set();

  for (const ev of events) {
    if (ev.event === 'step.enter') {
      active.add(ev.step);
      completed.delete(ev.step);
    } else if (ev.event === 'step.exit') {
      active.delete(ev.step);
      completed.add(ev.step);
    }
  }

  const states = {};
  for (const n of NODES) {
    if (active.has(n.id)) states[n.id] = 'active';
    else if (completed.has(n.id)) states[n.id] = 'completed';
    else states[n.id] = 'idle';
  }

  // DR is conditional — only required if it was ever launched
  const drLaunched = events.some(ev => ev.event === 'step.enter' && ev.step === 'DR');
  const required = drLaunched ? ['DR', 'BI'] : ['BI'];

  // CONV lights up when all launched parallel agents complete
  if (required.every(s => completed.has(s))) {
    states['CONV'] = 'active';
  }
  if (completed.has('AF') && required.every(s => completed.has(s))) {
    states['CONV'] = 'completed';
  }

  return states;
}

// Map raw events → sequence diagram messages
function deriveMessages(events) {
  const msgs = [];
  for (const ev of events) {
    switch (ev.event) {
      case 'message.user':
        msgs.push({
          from: 'user', to: 'rose',
          label: (ev.payload?.preview || 'Message').slice(0, 60),
          ts: ev.ts, color: '#F472B6',
        });
        break;
      case 'step.enter':
        if (ev.step === 'FP') {
          msgs.push({ from: 'user', to: 'rose', label: 'Feature prompt', ts: ev.ts, color: '#F472B6' });
        } else if (ev.step === 'AF') {
          msgs.push({ from: 'rose', to: 'rose', label: 'Reading codebase…', ts: ev.ts, color: '#A855F7', self: true });
        } else if (ev.step === 'DR') {
          msgs.push({ from: 'rose', to: 'rose-research', label: 'Launch: deep research', ts: ev.ts, color: '#A855F7' });
        } else if (ev.step === 'BI') {
          msgs.push({ from: 'rose', to: 'rose-backlog', label: 'Launch: backlog inspect', ts: ev.ts, color: '#A855F7' });
        }
        break;
      case 'step.exit':
        if (ev.step === 'DR') {
          msgs.push({ from: 'rose-research', to: 'rose', label: 'Research complete', ts: ev.ts, color: '#00FF88' });
        } else if (ev.step === 'BI') {
          msgs.push({ from: 'rose-backlog', to: 'rose', label: 'Backlog complete', ts: ev.ts, color: '#FF2222' });
        }
        break;
      case 'message.agent':
        msgs.push({ from: 'rose', to: 'user', label: (ev.payload?.preview || 'Response').slice(0, 60), ts: ev.ts, color: '#CC00FF' });
        break;
      default:
        break;
    }
  }
  return msgs;
}

function fmtTs(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleTimeString('en-GB', { hour12: false });
  } catch {
    return '';
  }
}

// ─── State Machine ──────────────────────────────────────────────────────────

function NodePulseRings({ node }) {
  const color = node.stepColor;
  const isLarge = node.r >= 38;
  return (
    <>
      <circle
        cx={node.cx} cy={node.cy} r={node.r}
        fill="none" stroke={color} strokeWidth={2} opacity={0}
        className={isLarge ? 'pulse-ring-1' : 'pulse-ring-sm-1'}
      />
      <circle
        cx={node.cx} cy={node.cy} r={node.r}
        fill="none" stroke={color} strokeWidth={1.5} opacity={0}
        className={isLarge ? 'pulse-ring-2' : 'pulse-ring-sm-2'}
      />
    </>
  );
}

function SMNode({ node, state, filterId }) {
  const isActive = state === 'active';
  const isCompleted = state === 'completed';
  const color = node.stepColor;
  const labelLines = node.label.split('\n');

  // Idle: clearly visible ring + fill. Completed: brighter. Active: full saber glow.
  const fillOpacity   = isActive ? 0.35 : isCompleted ? 0.22 : 0.18;
  const strokeOpacity = isActive ? 1    : isCompleted ? 0.85 : 0.65;
  const strokeWidth   = isActive ? 2.5  : 1.5;
  // Labels always white — colour only used as accent for active state
  const textFill = isActive ? '#ffffff' : isCompleted ? 'rgba(255,255,255,0.9)' : 'rgba(255,255,255,0.8)';
  const descFill = isActive ? 'rgba(255,255,255,0.75)' : 'rgba(255,255,255,0.55)';

  return (
    <g filter={isActive ? `url(#${filterId})` : undefined}>
      {isActive && <NodePulseRings node={node} />}

      {/* Soft inner glow for active nodes */}
      {isActive && !node.convergence && (
        <circle
          cx={node.cx} cy={node.cy} r={node.r + 4}
          fill={color} fillOpacity={0.12}
          stroke="none"
        />
      )}

      {/* Main circle */}
      <circle
        cx={node.cx} cy={node.cy} r={node.r}
        fill={node.convergence ? 'none' : color}
        fillOpacity={node.convergence ? 0 : fillOpacity}
        stroke={color}
        strokeWidth={strokeWidth}
        strokeOpacity={strokeOpacity}
        className={isActive ? 'node-active-circle' : ''}
      />

      {/* Labels above */}
      {node.label && labelLines.map((line, i) => (
        <text
          key={i}
          x={node.cx}
          y={node.cy - node.r - (labelLines.length > 1 ? 24 : 14) + i * 15}
          textAnchor="middle"
          fill={textFill}
          fontSize={10}
          fontFamily="IBM Plex Mono, monospace"
          fontWeight={600}
          letterSpacing="0.1em"
        >
          {line}
        </text>
      ))}

      {/* Descriptions below */}
      {node.desc.map((line, i) => (
        <text
          key={i}
          x={node.cx}
          y={node.cy + node.r + 18 + i * 14}
          textAnchor="middle"
          fill={descFill}
          fontSize={9}
          fontFamily="IBM Plex Mono, monospace"
        >
          {line}
        </text>
      ))}
    </g>
  );
}

function StateMachine({ nodeStates }) {
  // Which edges are lit (from-node active or completed)
  const activeEdgeIds = new Set();
  const edgeColorMap = {};
  for (const edge of EDGES) {
    const fromNode = NODE_MAP[edge.from];
    const fromState = nodeStates[edge.from] || 'idle';
    if (fromState === 'active' || fromState === 'completed') {
      activeEdgeIds.add(edge.id);
      edgeColorMap[edge.id] = fromNode.stepColor;
    }
  }

  return (
    <svg viewBox="0 0 800 520" className="sm-svg" style={{ display: 'block' }}>
      <defs>
        {/* Per-colour saber glow filters */}
        {NODES.map(node => (
          <filter key={node.id} id={`glow-${node.id}`} x="-80%" y="-80%" width="260%" height="260%">
            <feGaussianBlur in="SourceGraphic" stdDeviation="6" result="blur" />
            <feMerge>
              <feMergeNode in="blur" />
              <feMergeNode in="blur" />
              <feMergeNode in="SourceGraphic" />
            </feMerge>
          </filter>
        ))}
      </defs>

      {/* Space-black background */}
      <rect width="800" height="520" fill="#03030A" />

      {/* Edges */}
      {EDGES.map(edge => {
        const isActive = activeEdgeIds.has(edge.id);
        const edgeColor = edgeColorMap[edge.id] || 'rgba(255,255,255,0.15)';
        return (
          <path
            key={edge.id}
            d={edge.d}
            fill="none"
            stroke={isActive ? edgeColor : 'rgba(255,255,255,0.12)'}
            strokeWidth={isActive ? 1.5 : 1}
            strokeOpacity={isActive ? 0.7 : 1}
            strokeDasharray={edge.dashed ? '6 4' : 'none'}
            className={isActive && edge.dashed ? 'edge-active' : ''}
          />
        );
      })}

      {/* Nodes (rendered after edges so they sit on top) */}
      {NODES.map(node => (
        <SMNode
          key={node.id}
          node={node}
          state={nodeStates[node.id] || 'idle'}
          filterId={`glow-${node.id}`}
        />
      ))}
    </svg>
  );
}

// ─── Sequence Diagram ───────────────────────────────────────────────────────

const COL_W = 140;  // width per actor column
const ROW_H = 58;
const HEADER_H = 82;
const TS_W = 58;
const PADDING_L = 8;

function SequenceDiagram({ events }) {
  const seqRef = useRef(null);
  const messages = useMemo(() => deriveMessages(events), [events]);
  const prevLen = useRef(0);

  useEffect(() => {
    if (messages.length > prevLen.current && seqRef.current) {
      seqRef.current.scrollTop = seqRef.current.scrollHeight;
    }
    prevLen.current = messages.length;
  }, [messages.length]);

  const totalW = TS_W + PADDING_L + ACTORS.length * COL_W;
  const svgH = HEADER_H + messages.length * ROW_H;

  return (
    <div id="seq-container" ref={seqRef} style={{ overflow: 'auto', height: '100%' }}>
      <svg
        width="100%"
        viewBox={`0 0 ${totalW} ${Math.max(svgH, 300)}`}
        style={{ minHeight: '300px', display: 'block' }}
        fontFamily="IBM Plex Mono, monospace"
      >
        {/* Actor headers */}
        {ACTORS.map((actor, i) => {
          const cx = TS_W + PADDING_L + i * COL_W + COL_W / 2;
          return (
            <g key={actor.id}>
              {/* Saber glow halo */}
              <circle cx={cx} cy={30} r={22} fill={actor.color} fillOpacity={0.08} stroke="none" />
              {/* Outer ring */}
              <circle cx={cx} cy={30} r={19} fill="none" stroke={actor.color} strokeWidth={1} strokeOpacity={0.4} />
              {/* Inner filled circle */}
              <circle cx={cx} cy={30} r={17} fill={actor.color} fillOpacity={0.2} stroke={actor.color} strokeWidth={2} strokeOpacity={0.9} />
              {/* Initials */}
              <text x={cx} y={35} textAnchor="middle" fill={actor.color} fontSize={11} fontWeight={700} letterSpacing="0.04em" fontFamily="IBM Plex Mono, monospace">
                {actor.label.split(' ').map(w => w[0]).join('').slice(0, 2)}
              </text>
              {/* Actor label below — always white so it's actually readable */}
              <text x={cx} y={60} textAnchor="middle" fill="rgba(255,255,255,0.85)" fontSize={9} letterSpacing="0.1em" fontFamily="IBM Plex Mono, monospace">
                {actor.label}
              </text>
            </g>
          );
        })}

        {/* Lifelines */}
        {ACTORS.map((actor, i) => {
          const cx = TS_W + PADDING_L + i * COL_W + COL_W / 2;
          return (
            <line
              key={actor.id}
              x1={cx} y1={HEADER_H}
              x2={cx} y2={Math.max(svgH, 300)}
              stroke={actor.color}
              strokeWidth={1}
              strokeOpacity={0.18}
              strokeDasharray="3 5"
            />
          );
        })}

        {/* Separator */}
        <line
          x1={0} y1={HEADER_H - 2}
          x2={totalW} y2={HEADER_H - 2}
          stroke="rgba(255,255,255,0.06)" strokeWidth={1}
        />

        {/* Message rows */}
        {messages.map((msg, idx) => {
          const y = HEADER_H + idx * ROW_H + ROW_H / 2;
          const fromIdx = ACTORS.findIndex(a => a.id === msg.from);
          const toIdx = ACTORS.findIndex(a => a.id === msg.to);
          const fromX = TS_W + PADDING_L + fromIdx * COL_W + COL_W / 2;
          const toX = TS_W + PADDING_L + toIdx * COL_W + COL_W / 2;
          const color = msg.color;
          const isSelf = msg.self || msg.from === msg.to;

          return (
            <g key={idx} style={{ animation: 'row-in 0.25s ease-out' }}>
              {/* Timestamp */}
              <text
                x={4} y={y + 4}
                fill="rgba(255,255,255,0.5)"
                fontSize={9}
                fontFamily="IBM Plex Mono, monospace"
              >
                {fmtTs(msg.ts)}
              </text>

              {/* Active lifeline highlight */}
              <rect
                x={TS_W + PADDING_L + fromIdx * COL_W + COL_W / 2 - 3}
                y={HEADER_H + idx * ROW_H}
                width={6} height={ROW_H}
                fill={color} fillOpacity={0.08}
              />

              {isSelf ? (
                /* Self-message: bracket on the right of the lifeline */
                <>
                  <path
                    d={`M ${fromX} ${y - 8} L ${fromX + 28} ${y - 8} L ${fromX + 28} ${y + 8} L ${fromX} ${y + 8}`}
                    fill="none" stroke={color} strokeWidth={1} strokeOpacity={0.55}
                  />
                  <text x={fromX + 32} y={y + 4} fill={color} fillOpacity={1} fontSize={10} fontFamily="IBM Plex Mono, monospace">
                    {msg.label}
                  </text>
                </>
              ) : (
                /* Arrow from → to */
                <>
                  {/* Glow copy (blurred, wider) */}
                  <line
                    x1={fromX} y1={y}
                    x2={toX - (fromX < toX ? 6 : -6)} y2={y}
                    stroke={color} strokeWidth={4} strokeOpacity={0.18}
                  />
                  {/* Main shaft */}
                  <line
                    x1={fromX} y1={y}
                    x2={toX - (fromX < toX ? 6 : -6)} y2={y}
                    stroke={color} strokeWidth={1.5} strokeOpacity={0.9}
                  />
                  {/* Arrowhead */}
                  {fromX < toX ? (
                    <polygon points={`${toX},${y} ${toX - 9},${y - 4} ${toX - 9},${y + 4}`} fill={color} />
                  ) : (
                    <polygon points={`${toX},${y} ${toX + 9},${y - 4} ${toX + 9},${y + 4}`} fill={color} />
                  )}
                  {/* Label */}
                  <text
                    x={(fromX + toX) / 2} y={y - 9}
                    textAnchor="middle"
                    fill="#ffffff" fillOpacity={0.9} fontSize={10}
                    fontFamily="IBM Plex Mono, monospace"
                  >
                    {msg.label}
                  </text>
                </>
              )}
            </g>
          );
        })}

        {messages.length === 0 && (
          <text
            x={totalW / 2} y={200}
            textAnchor="middle"
            fill="rgba(0,180,255,0.5)"
            fontSize={12} letterSpacing="0.25em"
            fontFamily="IBM Plex Mono, monospace"
          >
            AWAITING EVENTS
          </text>
        )}
      </svg>
    </div>
  );
}

// ─── Sidebar ────────────────────────────────────────────────────────────────

function Sidebar({ sessions, selectedId, onSelect }) {
  const sorted = [...sessions].sort((a, b) => {
    const ta = a.started_at || '';
    const tb = b.started_at || '';
    return tb.localeCompare(ta);
  });

  function sessionTitle(s) {
    if (s.title) return s.title;
    const b = s.branch || '';
    if (b && b !== 'main' && b !== 'master') return b;
    return s.session_id?.slice(0, 12) || 'session';
  }

  return (
    <div id="sidebar">
      <div id="sidebar-header">rose observe</div>
      {sorted.length === 0 && (
        <div className="sidebar-empty">no sessions</div>
      )}
      {sorted.map(s => (
        <div
          key={s.session_id}
          className={`session-row ${s.session_id === selectedId ? 'selected' : ''}`}
          onClick={() => onSelect(s.session_id)}
        >
          <div className={`session-row-dot ${s.status === 'ready' ? 'live' : ''}`} />
          <div className="session-row-body">
            <div className="session-row-title">{sessionTitle(s)}</div>
            <div className="session-row-sub">
              {s.current_step ? `↳ ${s.current_step}` : s.status}
              {s.started_at ? `  ${fmtTs(s.started_at)}` : ''}
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

// ─── App ────────────────────────────────────────────────────────────────────

function App() {
  const [sessions, setSessions] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [events, setEvents] = useState([]);

  const sessionWsRef = useRef(null);
  const eventWsRef = useRef(null);
  const lastSeqRef = useRef(0);

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
            // Auto-select the most recent in-progress session
            setSelectedId(prev => {
              if (prev) return prev;
              const live = data.filter(s => s.status === 'ready');
              live.sort((a, b) => (b.started_at || '').localeCompare(a.started_at || ''));
              return live[0]?.session_id || data[0]?.session_id || null;
            });
          } else {
            // Single session update
            setSessions(prev => {
              const idx = prev.findIndex(s => s.session_id === data.session_id);
              if (idx >= 0) {
                const next = [...prev];
                next[idx] = data;
                return next;
              }
              return [...prev, data];
            });
            // Auto-select if nothing is currently selected
            setSelectedId(prev => prev || data.session_id);
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

  // Connect to event stream for selected session
  useEffect(() => {
    eventWsRef.current?.close();
    if (!selectedId) return;

    function connectEvents() {
      // Reset on every (re)connect — server always replays from seq 1
      setEvents([]);
      lastSeqRef.current = 0;

      const ws = new WebSocket(`${WS_BASE}/ws/events/${selectedId}`);
      eventWsRef.current = ws;

      ws.onmessage = (e) => {
        try {
          const ev = JSON.parse(e.data);
          if (ev.seq != null && ev.seq <= lastSeqRef.current) return;
          if (ev.seq != null) lastSeqRef.current = ev.seq;
          setEvents(prev => [...prev, ev]);
        } catch {}
      };

      ws.onclose = () => {
        setTimeout(connectEvents, 2000);
      };
    }
    connectEvents();
    return () => eventWsRef.current?.close();
  }, [selectedId]);

  const nodeStates = useMemo(() => deriveNodeStates(events), [events]);

  return (
    <div id="layout">
      <Sidebar
        sessions={sessions}
        selectedId={selectedId}
        onSelect={(id) => { setSelectedId(id); setEvents([]); }}
      />
      <div id="main">
        <div id="state-panel">
          {selectedId
            ? <StateMachine nodeStates={nodeStates} />
            : <div className="placeholder">select a session</div>
          }
        </div>
        <div id="sequence-panel">
          {selectedId
            ? <SequenceDiagram events={events} />
            : <div className="placeholder">select a session</div>
          }
        </div>
      </div>
    </div>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
