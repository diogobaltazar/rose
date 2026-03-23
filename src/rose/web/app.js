mermaid.initialize({ startOnLoad: false, theme: 'default' });

const DIAGRAM_DEF = `stateDiagram-v2
    direction TB

    state "Entry Points" as entry {
        E1: E1 — Feature idea
        E2: E2 — Bug report
        E3: E3 — Dependency upgrade
        E4: E4 — Spike / investigation
        E5: E5 — Autonomous pickup [future]
    }

    state "Requirements Pipeline" as pipeline {
        R1: R1 — Clarify intent
        R2: R2 — Requirements & acceptance criteria
        R3: R3 — Issue matching
        R4: R4 — Technical feasibility
        R5: R5 — Spec reconciliation

        R1 --> R2: user confirms intent
        R1 --> R1: analyst asks follow-up
        R2 --> R2: analyst refines criteria
        R2 --> R3: user confirms requirements
        R3 --> R3: analyst suggests overlaps
        R3 --> R4: user validates issue mapping
        R4 --> R2: feasibility concern revises requirements
        R4 --> R5: feasible, proceed
        R5 --> R5: conflict — user resolves
    }

    state decision <<choice>>

    state "Investigation" as investigation {
        W1: W1 — Write-up
    }

    state "Delivery Pipeline" as delivery {
        D1: D1 — Issue creation
        D2: D2 — Worktree setup
        D3: D3 — Implementation
        D4: D4 — Verification
        D5: D5 — Commit sorting
        D6: D6 — PR creation / update
        D7: D7 — Adjacent work detection
        P2: P2 — Merge PR

        D1 --> D2
        D2 --> D3
        D3 --> D4
        D4 --> D3: implementation failure
        D4 --> D5: verification passes
        D5 --> D6
        D6 --> D7
        D7 --> D1: separate unit — new issue
        D7 --> P2: PR ready
    }

    S1: S1 — Stakeholder input [interrupt]
    V1: V1 — State visualisation [future]

    E1 --> R1
    E2 --> R1
    E3 --> R1
    E4 --> R1
    E5 --> R1

    R5 --> decision
    decision --> W1: investigation
    decision --> D1: delivery
    W1 --> [*]: write-up complete

    D4 --> R2: requirement failure
    P2 --> [*]: PR merged, issues closed

    S1 --> R1
    S1 --> R2
    S1 --> R3
    S1 --> R4
    S1 --> R5
    S1 --> D1
    S1 --> D3
    S1 --> D6`;

let sessions = {};
let selectedSessionId = null;

function repoBasename(path) {
  return path ? path.split('/').filter(Boolean).pop() || path : 'unknown';
}

function branchSlug(branch) {
  const match = branch && branch.match(/^feat\/\d+-(.+)$/);
  return match ? match[1] : branch || '';
}

function renderSidebar() {
  const container = document.getElementById('project-list');
  const byRepo = {};
  Object.values(sessions).forEach(s => {
    const key = s.repository || 'unknown';
    if (!byRepo[key]) byRepo[key] = [];
    byRepo[key].push(s);
  });

  container.innerHTML = '';

  Object.entries(byRepo).forEach(([repo, list]) => {
    const projectEl = document.createElement('div');
    projectEl.className = 'project';

    const title = document.createElement('div');
    title.className = 'project-title';
    title.textContent = repoBasename(repo);
    projectEl.appendChild(title);

    list.forEach(s => {
      const issueEl = document.createElement('div');
      issueEl.className = 'issue-row' + (s.session_id === selectedSessionId ? ' selected' : '');
      issueEl.dataset.sessionId = s.session_id;

      const dot = document.createElement('span');
      dot.className = 'pulse-dot';

      const label = document.createElement('span');
      const issueNum = s.issue && s.issue !== 'null' ? `#${s.issue} ` : '';
      label.textContent = issueNum + branchSlug(s.branch);

      issueEl.appendChild(dot);
      issueEl.appendChild(label);
      issueEl.addEventListener('click', () => selectIssue(s.session_id));
      projectEl.appendChild(issueEl);
    });

    container.appendChild(projectEl);
  });
}

async function selectIssue(sessionId) {
  selectedSessionId = sessionId;
  renderSidebar();

  const session = sessions[sessionId];
  if (!session) return;

  document.getElementById('diagram-placeholder').style.display = 'none';
  const container = document.getElementById('diagram-container');
  container.innerHTML = '';

  const { svg } = await mermaid.render('lifecycle-diagram', DIAGRAM_DEF);
  container.innerHTML = svg;

  if (session.current_step) {
    highlightStep(container, session.current_step);
  }
}

function highlightStep(container, stepCode) {
  const svgEl = container.querySelector('svg');
  if (!svgEl) return;

  svgEl.querySelectorAll('.active-node').forEach(el => el.classList.remove('active-node'));

  const textNodes = svgEl.querySelectorAll('text');
  textNodes.forEach(text => {
    if (text.textContent.trim() === stepCode) {
      const parent = text.closest('g');
      if (parent) parent.classList.add('active-node');
    }
  });
}

function updateSession(data) {
  if (Array.isArray(data)) {
    data.forEach(s => { sessions[s.session_id] = s; });
  } else {
    sessions[data.session_id] = { ...sessions[data.session_id], ...data };
  }

  renderSidebar();

  if (selectedSessionId && data.session_id === selectedSessionId) {
    const container = document.getElementById('diagram-container');
    const session = sessions[selectedSessionId];
    if (session && session.current_step) {
      highlightStep(container, session.current_step);
    }
  }
}

async function fetchSessions() {
  const res = await fetch('/api/sessions');
  const data = await res.json();
  data.forEach(s => { sessions[s.session_id] = s; });
  renderSidebar();
}

function connectWebSocket() {
  const ws = new WebSocket(`ws://${location.host}/ws`);

  ws.addEventListener('message', event => {
    const data = JSON.parse(event.data);
    updateSession(data);
  });

  ws.addEventListener('close', () => {
    setTimeout(connectWebSocket, 3000);
  });
}

fetchSessions().then(connectWebSocket);
