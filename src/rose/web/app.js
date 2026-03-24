const { useState, useEffect, useRef, useMemo } = React;

// ─── Step metadata ────────────────────────────────────────────────────────────

const STEP_LABELS = {
  E1:'Feature idea',    E2:'Bug report',      E3:'Dependency upg.',
  E4:'Spike / invest.', E5:'Autonomous',
  R1:'Clarify intent',  R2:'Requirements',    R3:'Issue matching',
  R4:'Feasibility',     R5:'Spec reconcile',
  D1:'Issue creation',  D2:'Worktree setup',  D3:'Implementation',
  D4:'Verification',    D5:'Commit sorting',  D6:'PR creation',
  D7:'Adjacent work',   P2:'Merge PR',
  W1:'Write-up',        S1:'Stakeholder',
};

// ─── State machine layout ─────────────────────────────────────────────────────
// Each node: cx/cy = centre. Rect = 82 × 26 px.

const NW = 82, NH = 26;

const SM = {
  E1:{cx:52, cy:36},  E2:{cx:142,cy:36},  E3:{cx:232,cy:36},
  E4:{cx:52, cy:68},  E5:{cx:142,cy:68},
  R1:{cx:190,cy:120}, R2:{cx:190,cy:158}, R3:{cx:190,cy:196},
  R4:{cx:190,cy:234}, R5:{cx:190,cy:272},
  W1:{cx:88, cy:340},
  D1:{cx:302,cy:340}, D2:{cx:302,cy:378}, D3:{cx:302,cy:416},
  D4:{cx:302,cy:454}, D5:{cx:302,cy:492}, D6:{cx:302,cy:530},
  D7:{cx:302,cy:568}, P2:{cx:302,cy:606},
  S1:{cx:20, cy:196},
};

const DIA = { cx:190, cy:308, r:13 }; // decision diamond

const nl = (c) => SM[c].cx;          // node left-centre x
const nr = (c) => SM[c].cx + NW/2;   // node right edge x
const nle = (c) => SM[c].cx - NW/2;  // node left edge x
const nt = (c) => SM[c].cy - NH/2;   // node top edge y
const nb = (c) => SM[c].cy + NH/2;   // node bottom edge y
const nm = (c) => SM[c].cy;          // node mid y
const nc = (c) => SM[c].cx;          // node centre x

// ─── Sequence diagram constants ───────────────────────────────────────────────

const ACTORS  = ['user','orchestrator','analyst','engineer','git','github'];
const ACTOR_X = { user:75, orchestrator:195, analyst:330, engineer:460, git:570, github:680 };
const SEQ_W   = 760;
const ROW_H   = 36;
const HDR_H   = 56;

function ax(name) {
  return ACTOR_X[name] ?? 680;
}

// ─── Hooks ────────────────────────────────────────────────────────────────────

function useSessions() {
  const [sessions, setSessions] = useState({});

  useEffect(() => {
    fetch('/api/sessions')
      .then(r => r.json())
      .then(data => {
        const m = {};
        data.forEach(s => { m[s.session_id] = s; });
        setSessions(m);
      })
      .catch(() => {});

    let ws;
    function connect() {
      ws = new WebSocket(`ws://${location.host}/ws`);
      ws.onmessage = e => {
        const data = JSON.parse(e.data);
        const arr = Array.isArray(data) ? data : [data];
        setSessions(prev => {
          const next = { ...prev };
          arr.forEach(s => { next[s.session_id] = { ...next[s.session_id], ...s }; });
          return next;
        });
      };
      ws.onclose = () => setTimeout(connect, 3000);
    }
    connect();
    return () => ws && ws.close();
  }, []);

  return sessions;
}

function useEventStream(sessionId) {
  const [events, setEvents] = useState([]);

  useEffect(() => {
    setEvents([]);
    if (!sessionId) return;
    const ws = new WebSocket(`ws://${location.host}/ws/events/${sessionId}`);
    ws.onmessage = e => {
      try { setEvents(prev => [...prev, JSON.parse(e.data)]); } catch(_) {}
    };
    return () => ws.close();
  }, [sessionId]);

  return events;
}

// ─── Utilities ────────────────────────────────────────────────────────────────

function repoName(path) {
  return path ? path.split('/').filter(Boolean).pop() || path : 'unknown';
}

function branchSlug(branch) {
  const m = branch && branch.match(/^feat\/\d+-(.+)$/);
  return m ? m[1] : (branch || '');
}

function deriveActiveStep(events) {
  const stack = [];
  for (const e of events) {
    if (e.event === 'step.enter') {
      const s = e.step || e.payload?.step;
      if (s) stack.push(s);
    } else if (e.event === 'step.exit' && stack.length) {
      stack.pop();
    }
  }
  return stack[stack.length - 1] ?? null;
}

// ─── Sidebar ──────────────────────────────────────────────────────────────────

function Sidebar({ sessions, selectedId, onSelect }) {
  const byRepo = useMemo(() => {
    const m = {};
    Object.values(sessions).forEach(s => {
      const k = s.repository || 'unknown';
      (m[k] = m[k] || []).push(s);
    });
    return m;
  }, [sessions]);

  return (
    <aside id="sidebar">
      <h1>rose observe</h1>
      {Object.entries(byRepo).map(([repo, list]) => (
        <div className="project" key={repo}>
          <div className="project-title">{repoName(repo)}</div>
          {list.map(s => {
            const num  = s.issue && s.issue !== 'null' ? `#${s.issue} ` : '';
            const slug = branchSlug(s.branch) || s.session_id.slice(0, 8);
            return (
              <div
                key={s.session_id}
                className={`issue-row${s.session_id === selectedId ? ' selected' : ''}`}
                onClick={() => onSelect(s.session_id)}
              >
                <span className="pulse-dot" />
                <span>{num}{slug}</span>
              </div>
            );
          })}
        </div>
      ))}
    </aside>
  );
}

// ─── State Machine ────────────────────────────────────────────────────────────

function SMNode({ code, active }) {
  const { cx, cy } = SM[code];
  const on = active === code;
  return (
    <g className={on ? 'sm-node-active' : ''}>
      <rect x={cx-NW/2} y={cy-NH/2} width={NW} height={NH} className="sm-node-rect" rx={0} />
      <text x={cx} y={cy-4}  textAnchor="middle" className="sm-node-code">{code}</text>
      <text x={cx} y={cy+8}  textAnchor="middle" className="sm-node-desc">{STEP_LABELS[code]||''}</text>
    </g>
  );
}

function line(x1,y1,x2,y2,cls) {
  return <line x1={x1} y1={y1} x2={x2} y2={y2} className={cls||'sm-edge'} markerEnd="url(#sm-arr)" />;
}

function curve(d, cls) {
  return <path d={d} className={cls||'sm-edge'} markerEnd="url(#sm-arr)" fill="none" />;
}

function StateMachine({ activeStep }) {
  return (
    <svg viewBox="0 0 380 660" style={{width:'100%', maxWidth:380, overflow:'visible'}}>
      <defs>
        <marker id="sm-arr" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 z" fill="#1a2035" />
        </marker>
        <marker id="sm-arr-s1" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 z" fill="#4b5563" opacity="0.5" />
        </marker>
      </defs>

      {/* Group labels */}
      <text x={142} y={14}  className="sm-group-label" textAnchor="middle">entry points</text>
      <text x={190} y={103} className="sm-group-label" textAnchor="middle">requirements</text>
      <text x={88}  y={323} className="sm-group-label" textAnchor="middle">investigation</text>
      <text x={302} y={323} className="sm-group-label" textAnchor="middle">delivery</text>

      {/* E → R1 */}
      {['E1','E2','E3','E4','E5'].map(e =>
        <path key={e} d={`M${nc(e)} ${nb(e)} L${nc('R1')} ${nt('R1')}`}
          className="sm-edge" markerEnd="url(#sm-arr)" fill="none" />
      )}

      {/* Requirements chain */}
      {[['R1','R2'],['R2','R3'],['R3','R4'],['R4','R5']].map(([a,b]) =>
        <path key={a+b} d={`M${nc(a)} ${nb(a)} L${nc(b)} ${nt(b)}`}
          className="sm-edge" markerEnd="url(#sm-arr)" fill="none" />
      )}

      {/* Self-loops (left arc) */}
      {['R1','R2','R3','R5'].map(r =>
        <path key={r+'-self'}
          d={`M${nle(r)} ${nm(r)-5} C${nle(r)-24} ${nm(r)-20} ${nle(r)-24} ${nm(r)+20} ${nle(r)} ${nm(r)+5}`}
          className="sm-edge" markerEnd="url(#sm-arr)" fill="none" />
      )}

      {/* R4 → R2 (feasibility loop, arc left) */}
      <path d={`M${nle('R4')} ${nm('R4')} C${nle('R4')-44} ${nm('R4')} ${nle('R2')-44} ${nm('R2')} ${nle('R2')} ${nm('R2')}`}
        className="sm-edge" markerEnd="url(#sm-arr)" fill="none" />

      {/* R5 → decision */}
      <path d={`M${nc('R5')} ${nb('R5')} L${DIA.cx} ${DIA.cy-DIA.r}`}
        className="sm-edge" markerEnd="url(#sm-arr)" fill="none" />

      {/* Decision → W1, D1 */}
      <path d={`M${DIA.cx-DIA.r} ${DIA.cy} L${nc('W1')} ${nt('W1')}`}
        className="sm-edge" markerEnd="url(#sm-arr)" fill="none" />
      <path d={`M${DIA.cx+DIA.r} ${DIA.cy} L${nc('D1')} ${nt('D1')}`}
        className="sm-edge" markerEnd="url(#sm-arr)" fill="none" />

      {/* Delivery chain */}
      {[['D1','D2'],['D2','D3'],['D3','D4'],['D4','D5'],['D5','D6'],['D6','D7'],['D7','P2']].map(([a,b]) =>
        <path key={a+b} d={`M${nc(a)} ${nb(a)} L${nc(b)} ${nt(b)}`}
          className="sm-edge" markerEnd="url(#sm-arr)" fill="none" />
      )}

      {/* D4 → D3 loop (arc right) */}
      <path d={`M${nr('D4')} ${nm('D4')} C${nr('D4')+30} ${nm('D4')} ${nr('D3')+30} ${nm('D3')} ${nr('D3')} ${nm('D3')}`}
        className="sm-edge" markerEnd="url(#sm-arr)" fill="none" />

      {/* D4 → R2 requirement failure (long arc left) */}
      <path d={`M${nle('D4')} ${nm('D4')} C${nle('D4')-55} ${nm('D4')} ${nle('R2')-55} ${nm('R2')} ${nle('R2')} ${nm('R2')}`}
        className="sm-edge" markerEnd="url(#sm-arr)" fill="none" />

      {/* D7 → D1 new issue (arc right, up) */}
      <path d={`M${nr('D7')} ${nm('D7')} C${nr('D7')+40} ${nm('D7')} ${nr('D1')+40} ${nm('D1')} ${nr('D1')} ${nm('D1')}`}
        className="sm-edge" markerEnd="url(#sm-arr)" fill="none" />

      {/* S1 dashed fan-out */}
      {['R1','R2','R3','R4','R5','D1','D3','D6'].map(t =>
        <path key={'S1-'+t}
          d={`M${nr('S1')} ${nm('S1')} C${nr('S1')+28} ${nm('S1')} ${nle(t)-8} ${nm(t)} ${nle(t)} ${nm(t)}`}
          className="sm-edge-s1" markerEnd="url(#sm-arr-s1)" fill="none" />
      )}

      {/* Decision diamond */}
      <polygon
        className="sm-diamond"
        points={`${DIA.cx},${DIA.cy-DIA.r} ${DIA.cx+DIA.r},${DIA.cy} ${DIA.cx},${DIA.cy+DIA.r} ${DIA.cx-DIA.r},${DIA.cy}`}
      />

      {/* Terminals */}
      <line x1={nc('W1')} y1={nb('W1')} x2={nc('W1')} y2={nb('W1')+16} className="sm-edge" />
      <circle cx={nc('W1')} cy={nb('W1')+22} r={5} className="sm-terminal" />
      <line x1={nc('P2')} y1={nb('P2')} x2={nc('P2')} y2={nb('P2')+16} className="sm-edge" />
      <circle cx={nc('P2')} cy={nb('P2')+22} r={5} className="sm-terminal" />

      {/* Nodes (drawn last, on top of edges) */}
      {Object.keys(SM).map(code => <SMNode key={code} code={code} active={activeStep} />)}
    </svg>
  );
}

// ─── Sequence Diagram ─────────────────────────────────────────────────────────

function eventToRow(evt) {
  const { event, agent, step, payload } = evt;
  switch (event) {
    case 'session.start':
      return { kind:'banner', text:'── session started ──', dim:true };
    case 'session.end':
      return { kind:'banner', text:`── session ended · ${payload?.outcome||''} ──`, dim:true };
    case 'step.enter':
      return { kind:'arrow',  from:'orchestrator', to:agent||'orchestrator',
               label:`${step}: ${STEP_LABELS[step]||step}`, openStep:step };
    case 'step.exit':
      return { kind:'return', from:agent||'orchestrator', to:'orchestrator',
               label:`done · ${payload?.outcome||''}`, closeStep:step };
    case 'message.user':
      return { kind:'arrow',  from:'user', to:agent||'orchestrator',
               label:(payload?.preview||'').slice(0,46) };
    case 'message.agent':
      return { kind:'return', from:agent||'orchestrator', to:'user',
               label:(payload?.preview||'').slice(0,46) };
    case 'tool.call':
      return { kind:'self',   actor:agent||'orchestrator',
               label:payload?.tool||'tool' };
    case 'interrupt.s1':
      return { kind:'interrupt', text:`S1 · ${payload?.note||'stakeholder input'}` };
    case 'error':
      return { kind:'banner', text:`error · ${payload?.message||''}`, error:true };
    default:
      return null;
  }
}

function SequenceDiagram({ events }) {
  const containerRef = useRef(null);

  useEffect(() => {
    const el = containerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [events.length]);

  const { rows, bars } = useMemo(() => {
    const rows = [];
    const bars = [];          // {actor, startRow, endRow|null}
    const open = {};          // step -> bar index

    events.forEach(evt => {
      const row = eventToRow(evt);
      if (!row) return;
      const idx = rows.length;
      rows.push(row);

      if (row.openStep) {
        const bi = bars.length;
        bars.push({ actor: row.to, startRow: idx, endRow: null });
        open[row.openStep] = bi;
      }
      if (row.closeStep && open[row.closeStep] != null) {
        bars[open[row.closeStep]].endRow = idx;
        delete open[row.closeStep];
      }
    });
    return { rows, bars };
  }, [events]);

  const totalH  = HDR_H + rows.length * ROW_H + 48;
  const C = {
    border:  '#1a2035',
    dim:     '#1e293b',
    text:    '#94a3b8',
    dimText: '#4b5563',
    accent:  '#f59e0b',
    return:  '#475569',
    arrow:   '#64748b',
    font:    'IBM Plex Mono, Courier New, monospace',
  };

  function rowY(i) { return HDR_H + i * ROW_H + ROW_H / 2; }

  return (
    <div id="sequence-panel" ref={containerRef}>
      <svg width={SEQ_W} height={totalH} style={{display:'block', minWidth:SEQ_W}}>
        <defs>
          {/* Filled arrowhead */}
          <marker id="seq-f" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto">
            <path d="M0,0 L7,3.5 L0,7 z" fill={C.arrow} />
          </marker>
          {/* Open arrowhead */}
          <marker id="seq-o" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto">
            <path d="M0,0 L7,4 L0,8" fill="none" stroke={C.return} strokeWidth="1.2" />
          </marker>
        </defs>

        {/* Actor headers */}
        {ACTORS.map(a => (
          <g key={a}>
            <text x={ax(a)} y={26} textAnchor="middle"
              style={{fill:C.dimText, fontFamily:C.font, fontSize:9, letterSpacing:'0.12em'}}>
              {a}
            </text>
            {/* Lifeline */}
            <line x1={ax(a)} y1={40} x2={ax(a)} y2={totalH}
              stroke={C.dim} strokeWidth={1} strokeDasharray="4 4" />
          </g>
        ))}

        {/* Header rule */}
        <line x1={0} y1={40} x2={SEQ_W} y2={40} stroke={C.border} strokeWidth={1} />

        {/* Activation bars */}
        {bars.map((b, i) => {
          const y1 = HDR_H + b.startRow * ROW_H;
          const y2 = b.endRow != null ? HDR_H + b.endRow * ROW_H + ROW_H/2 : totalH - 24;
          return (
            <rect key={i} x={ax(b.actor)-4} y={y1} width={8} height={y2-y1}
              fill={C.accent} fillOpacity={0.13} />
          );
        })}

        {/* Event rows */}
        {rows.map((row, i) => {
          const cy = rowY(i);

          if (row.kind === 'banner') {
            return (
              <g key={i}>
                <rect x={0} y={cy-11} width={SEQ_W} height={22}
                  fill={row.error ? '#100404' : '#080b12'} />
                <line x1={0} y1={cy-11} x2={SEQ_W} y2={cy-11} stroke={C.border} strokeWidth={1} />
                <text x={SEQ_W/2} y={cy+4} textAnchor="middle"
                  style={{fill: row.error ? '#ef4444' : C.dimText,
                           fontFamily:C.font, fontSize:9, letterSpacing:'0.1em'}}>
                  {row.text}
                </text>
              </g>
            );
          }

          if (row.kind === 'interrupt') {
            return (
              <g key={i}>
                <rect x={0} y={cy-11} width={SEQ_W} height={22} fill="#100c00" />
                <line x1={0} y1={cy-11} x2={SEQ_W} y2={cy-11} stroke={C.accent} strokeWidth={1} strokeOpacity={0.3} />
                <text x={SEQ_W/2} y={cy+4} textAnchor="middle"
                  style={{fill:C.accent, fontFamily:C.font, fontSize:9, letterSpacing:'0.1em'}}>
                  {row.text}
                </text>
              </g>
            );
          }

          if (row.kind === 'self') {
            const x = ax(row.actor);
            return (
              <g key={i}>
                <path d={`M${x} ${cy-7} L${x+22} ${cy-7} L${x+22} ${cy+7} L${x} ${cy+7}`}
                  stroke={C.dim} strokeWidth={1} fill="none" markerEnd="url(#seq-f)" />
                <text x={x+26} y={cy+4}
                  style={{fill:C.dimText, fontFamily:C.font, fontSize:9}}>
                  {row.label}
                </text>
              </g>
            );
          }

          if (row.kind === 'arrow' || row.kind === 'return') {
            const fx = ax(row.from);
            const tx = ax(row.to);
            if (fx === tx) return null;
            const isRet = row.kind === 'return';
            const mid   = (fx + tx) / 2;
            return (
              <g key={i}>
                <line x1={fx} y1={cy} x2={tx} y2={cy}
                  stroke={isRet ? C.return : C.arrow} strokeWidth={1}
                  markerEnd={isRet ? 'url(#seq-o)' : 'url(#seq-f)'}
                  strokeDasharray={isRet ? '4 3' : undefined}
                />
                <text x={mid} y={cy-5} textAnchor="middle"
                  style={{fill:C.text, fontFamily:C.font, fontSize:9}}>
                  {row.label}
                </text>
              </g>
            );
          }

          return null;
        })}
      </svg>
    </div>
  );
}

// ─── App ──────────────────────────────────────────────────────────────────────

function App() {
  const sessions   = useSessions();
  const [selId, setSelId] = useState(null);
  const events     = useEventStream(selId);
  const activeStep = useMemo(() => deriveActiveStep(events), [events]);

  return (
    <div id="layout">
      <Sidebar sessions={sessions} selectedId={selId} onSelect={setSelId} />
      <div id="main">
        <div id="state-panel">
          <StateMachine activeStep={activeStep} />
        </div>
        {selId
          ? <SequenceDiagram events={events} />
          : <div id="sequence-panel"><div className="placeholder">select a session</div></div>
        }
      </div>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
