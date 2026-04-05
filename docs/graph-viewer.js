"use strict";

const defaultSource = String.raw`%%{init: {'flowchart': {'nodeSpacing': 28, 'rankSpacing': 42, 'curve': 'basis'}}}%%
graph LR
    FeatureRequest[Feature Request]
    TestFeature[Test Feature]
    WorkOnFeature[Work on Feature]
    AnalyseFeature[Analyse Feature]
    ClarifyFeature[Clarify Feature]
    DeepResearchTechnology[Deep Research on Technology]
    ClarifyArchitecture[Clarify Architecture]
    GitWorktreeInspect[Inspect Worktree]
    GitWorktreeCreate[Create Worktree]
    GitWorktreeDelete[Delete Worktree]
    GitSelectWorktree[Select Worktree]
    InspectCode[Inspect Sources]
    InspectBacklog[Inspect Backlog]
    CreateIssue[Create Issue]
    BranchIssue[Branch Issue]
    EditIssue[Edit Issue]
    DeleteIssue[Delete Issue]
    SelectIssue[Select Issue]
    GrantIssuePermission[Grant Issue Permission]
    GrantCodePermission[Grant Code Permission]
    GitHubPRInspect[Inspect PRs]
    GitSelectPR[Select PR]
    GitHubPRCreate[Create PR]
    GitHubPREdit[Update PR]
    GitHubPRClose[Close PR]
    GitHubPRMerge[Merge PR]
    ImplementFeature[Implement Feature]
    VerifyLocalRunAgent[Execute Local Run]
    ExecuteLocalRunUser[Execute Local Run]
    RunUnitTests[Run Unit Tests]
    RunIntegrationTests[Run Integration Tests]
    UpdateDocs[Update Docs]
    AssessTag[Assess Tag]
    ProposeTag[Propose Tag]
    ReviewLocalValidation[Review Local Validation]
    StructuredCommits[Structured Commits]
    PushCommits[Push Commits]
    DocumentPR[Document PR]
    SelectMergePR[Select Merge PR]
    ReportIssue[Report Issue]
    DebugFeature[Debug Feature]
    MonitorDeployment[Monitor Deployment]
    InspectPipeline[Inspect Pipeline]
    FixDeployment[Fix Deployment]
    UpdateIssueWithQuestion[Update Issue With Question]
    RequestUserAssistance[Request User Assistance]
    AnalysisReady(( ))
    ValidationReady(( ))

    FeatureRequest --- AnalyseFeature
    TestFeature --- GitHubPRInspect
    WorkOnFeature --- AnalyseFeature
    AnalyseFeature --- GitWorktreeInspect
    GrantCodePermission --- GitHubPRInspect
    GrantCodePermission --- GitWorktreeInspect

    GitWorktreeInspect --- GitWorktreeCreate
    GitWorktreeInspect --- GitWorktreeDelete
    GitWorktreeInspect --- GitSelectWorktree
    GitWorktreeCreate --- GitSelectWorktree
    GitHubPRInspect --- GitHubPRCreate
    GitHubPRInspect --- GitHubPREdit
    GitHubPRInspect --- GitHubPRClose
    GitHubPRInspect --- GitHubPRMerge
    GitHubPRInspect --- GitSelectPR
    AnalyseFeature --- InspectCode
    AnalyseFeature --- InspectBacklog
    InspectCode -.- AnalysisReady
    InspectBacklog -.- AnalysisReady
    AnalysisReady --- ClarifyFeature
    AnalysisReady --- DeepResearchTechnology
    DeepResearchTechnology --- ClarifyArchitecture
    AnalysisReady --- GrantIssuePermission
    AnalysisReady -.- SelectIssue
    GrantIssuePermission --- CreateIssue
    CreateIssue --- BranchIssue
    BranchIssue --- GrantCodePermission
    GrantIssuePermission --- EditIssue
    GrantIssuePermission --- DeleteIssue
    GrantIssuePermission -.- SelectIssue
    SelectIssue --- GrantCodePermission
    GitSelectPR --- GrantCodePermission

    GitSelectWorktree --- ImplementFeature
    GitSelectWorktree --- ExecuteLocalRunUser
    ImplementFeature --- VerifyLocalRunAgent
    ImplementFeature --- ExecuteLocalRunUser
    ImplementFeature --- RunUnitTests
    ImplementFeature --- RunIntegrationTests
    ImplementFeature --- UpdateDocs
    ImplementFeature --- AssessTag
    AssessTag --- ProposeTag

    VerifyLocalRunAgent -.- ValidationReady
    ExecuteLocalRunUser -.- ValidationReady
    RunUnitTests -.- ValidationReady
    RunIntegrationTests -.- ValidationReady
    UpdateDocs -.- ValidationReady
    ProposeTag -.- ValidationReady
    ValidationReady --- ReviewLocalValidation

    ReviewLocalValidation --- StructuredCommits
    ReviewLocalValidation --- SelectMergePR
    ReviewLocalValidation --- ReportIssue
    StructuredCommits --- PushCommits
    PushCommits --- GitHubPRCreate
    PushCommits --- GitHubPREdit
    ExecuteLocalRunUser --- ReviewLocalValidation
    GitHubPRCreate --- DocumentPR
    GitHubPREdit --- DocumentPR
    ExecuteLocalRunUser --- DocumentPR
    DocumentPR --- SelectMergePR
    SelectMergePR --- GitHubPRMerge
    ReportIssue --- AnalyseFeature
    ReportIssue --- DebugFeature
    DebugFeature --- ImplementFeature

    GitHubPRMerge --- AssessTag
    GitHubPRMerge --- MonitorDeployment
    ProposeTag --- MonitorDeployment
    MonitorDeployment --- InspectPipeline
    InspectPipeline --- FixDeployment
    InspectPipeline --- DeepResearchTechnology
    FixDeployment --- InspectCode
    FixDeployment --- DeepResearchTechnology
    FixDeployment --- CreateIssue
    FixDeployment --- GitWorktreeInspect
    FixDeployment --- ImplementFeature
    FixDeployment --- VerifyLocalRunAgent
    FixDeployment --- RunUnitTests
    FixDeployment --- RunIntegrationTests
    FixDeployment --- PushCommits
    FixDeployment --- GitHubPRCreate
    FixDeployment --- GitHubPREdit
    FixDeployment --- GitHubPRMerge
    FixDeployment --- ProposeTag
    FixDeployment --- UpdateIssueWithQuestion
    UpdateIssueWithQuestion --- RequestUserAssistance
    RequestUserAssistance --- DeepResearchTechnology

    classDef user fill:#d9ecff,stroke:#2b6cb0,color:#102a43
    classDef assistant fill:#e3f9e5,stroke:#2f855a,color:#1b4332
    classDef join fill:#f8fafc,stroke:#94a3b8,color:#f8fafc,stroke-width:2px

    class FeatureRequest,TestFeature,WorkOnFeature,GrantIssuePermission,GrantCodePermission user
    class ExecuteLocalRunUser user
    class ClarifyFeature,ClarifyArchitecture,ReviewLocalValidation,SelectMergePR,ReportIssue,RequestUserAssistance user
    class AnalyseFeature,DeepResearchTechnology,InspectCode,InspectBacklog,SelectIssue,CreateIssue assistant
    class EditIssue,DeleteIssue,BranchIssue,GitWorktreeInspect,GitWorktreeCreate,GitWorktreeDelete assistant
    class GitSelectWorktree,GitHubPRInspect,GitSelectPR,GitHubPRCreate,GitHubPREdit,GitHubPRClose assistant
    class GitHubPRMerge,ImplementFeature,VerifyLocalRunAgent,RunUnitTests assistant
    class RunIntegrationTests,UpdateDocs,AssessTag,ProposeTag,StructuredCommits,PushCommits assistant
    class DocumentPR,DebugFeature,MonitorDeployment,InspectPipeline,FixDeployment,UpdateIssueWithQuestion assistant
    class AnalysisReady,ValidationReady join`;

const SVG_NS = "http://www.w3.org/2000/svg";
const viewport = document.getElementById("viewport");
const edgeLayer = document.getElementById("edge-layer");
const nodeLayer = document.getElementById("node-layer");
const edgeHitLayer = document.getElementById("edge-hit-layer");
const svg = document.getElementById("graph");
const canvasBg = document.getElementById("canvas-bg");
const sourceInput = document.getElementById("source-input");
const selectionMeta = document.getElementById("selection-meta");
const neighborList = document.getElementById("neighbor-list");
const resetButton = document.getElementById("reset-button");
const fitButton = document.getElementById("fit-button");
const renderButton = document.getElementById("render-button");

sourceInput.value = defaultSource;

let graphState = null;
let panState = null;
let viewState = { scale: 1, x: 0, y: 0 };
let selectedNodeId = null;
let selectedEdgeId = null;

const tooltip = document.getElementById("tooltip");

function showTooltip(text, clientX, clientY) {
  if (!text) return;
  tooltip.innerHTML = text
    .split("\n")
    .map((line, i) => i === 0
      ? `<strong>${line}</strong>`
      : `<span style="opacity:0.75;font-size:0.84em">${line}</span>`)
    .join("<br>");
  tooltip.style.display = "block";
  positionTooltip(clientX, clientY);
}

function positionTooltip(clientX, clientY) {
  const pad = 14;
  const tw = tooltip.offsetWidth;
  const th = tooltip.offsetHeight;
  let left = clientX + pad;
  let top = clientY + pad;
  if (left + tw > window.innerWidth - pad) left = clientX - tw - pad;
  if (top + th > window.innerHeight - pad) top = clientY - th - pad;
  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${top}px`;
}

function hideTooltip() {
  tooltip.style.display = "none";
}

function getViewBoxMetrics() {
  const rect = svg.getBoundingClientRect();
  const box = svg.viewBox.baseVal;
  return {
    rect,
    box,
    scaleX: box.width / rect.width,
    scaleY: box.height / rect.height,
  };
}

function pointerToSvg(clientX, clientY) {
  const { rect, box, scaleX, scaleY } = getViewBoxMetrics();
  return {
    x: box.x + (clientX - rect.left) * scaleX,
    y: box.y + (clientY - rect.top) * scaleY,
  };
}

function parseStyle(styleText) {
  return styleText.split(",").reduce((style, part) => {
    const [key, value] = part.split(":");
    if (key && value) {
      style[key.trim()] = value.trim();
    }
    return style;
  }, {});
}

function getNodePalette(node) {
  if (node.shape === "join" || node.className === "join") {
    return {
      fill: "rgba(38, 17, 21, 0.92)",
      stroke: "#fda4af",
    };
  }

  if (node.className === "user") {
    return {
      fill: "rgba(94, 23, 29, 0.95)",
      stroke: "#f87171",
    };
  }

  return {
    fill: "rgba(40, 10, 60, 0.95)",
    stroke: "#c084fc",
  };
}

function parseMermaid(source) {
  const nodes = new Map();
  const edges = [];
  const classDefs = new Map();
  let nodeSequence = 0;

  const ensureNode = (id, shape = "rect") => {
    if (!nodes.has(id)) {
      nodes.set(id, {
        id,
        label: id,
        shape,
        className: null,
        sourceIndex: nodeSequence,
      });
      nodeSequence += 1;
    }
    return nodes.get(id);
  };

  const lines = source
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter((line) => line.length > 0);

  for (const line of lines) {
    if (line.startsWith("%%{") || line.startsWith("graph ")) {
      continue;
    }

    let match = line.match(/^classDef\s+([A-Za-z0-9_]+)\s+(.+)$/);
    if (match) {
      classDefs.set(match[1], parseStyle(match[2]));
      continue;
    }

    match = line.match(/^class\s+([A-Za-z0-9_,]+)\s+([A-Za-z0-9_]+)$/);
    if (match) {
      const ids = match[1].split(",");
      for (const id of ids) {
        ensureNode(id).className = match[2];
      }
      continue;
    }

    match = line.match(/^([A-Za-z0-9_]+)\[(.+)\]$/);
    if (match) {
      const node = ensureNode(match[1], "rect");
      node.label = match[2];
      continue;
    }

    match = line.match(/^([A-Za-z0-9_]+)\(\((.*)\)\)$/);
    if (match) {
      const node = ensureNode(match[1], "join");
      node.label = match[2].trim() || "";
      continue;
    }

    match = line.match(/^([A-Za-z0-9_]+)\s+(-{3}|-\.-)\s+([A-Za-z0-9_]+)$/);
    if (match) {
      ensureNode(match[1]);
      ensureNode(match[3]);
      edges.push({
        source: match[1],
        target: match[3],
        dashed: match[2] === "-.-",
      });
      continue;
    }

    // %% desc:NodeId: description text
    match = line.match(/^%%\s+desc:([A-Za-z0-9_]+):\s*(.+)$/);
    if (match) {
      ensureNode(match[1]).description = match[2].trim();
      continue;
    }

    // %% edge:SourceId:TargetId: description text
    match = line.match(/^%%\s+edge:([A-Za-z0-9_]+):([A-Za-z0-9_]+):\s*(.+)$/);
    if (match) {
      const key = `${match[1]}:${match[2]}`;
      edges._descMap = edges._descMap || new Map();
      edges._descMap.set(key, match[3].trim());
    }
  }

  const edgeDescMap = edges._descMap || new Map();
  delete edges._descMap;

  return {
    nodes: Array.from(nodes.values()).map((node) => {
      const palette = getNodePalette(node);
      return {
        ...node,
        fill: palette.fill,
        stroke: palette.stroke,
      };
    }),
    edges: edges.map((edge) => ({
      ...edge,
      description: edgeDescMap.get(`${edge.source}:${edge.target}`) ?? null,
    })),
  };
}

function classifyEdges(nodes, edges) {
  const nodeOrder = [...nodes].sort((a, b) => a.sourceIndex - b.sourceIndex);
  const incoming = new Map(nodes.map((node) => [node.id, 0]));
  const outgoing = new Map(nodes.map((node) => [node.id, []]));

  for (const edge of edges) {
    incoming.set(edge.target, (incoming.get(edge.target) || 0) + 1);
    outgoing.get(edge.source).push(edge);
    edge.isLoop = false;
  }

  const state = new Map(nodes.map((node) => [node.id, 0]));
  const roots = nodeOrder.filter((node) => (incoming.get(node.id) || 0) === 0);

  function visit(nodeId) {
    state.set(nodeId, 1);
    for (const edge of outgoing.get(nodeId)) {
      const targetState = state.get(edge.target) || 0;
      if (targetState === 1) {
        edge.isLoop = true;
        continue;
      }
      if (targetState === 0) {
        visit(edge.target);
      }
    }
    state.set(nodeId, 2);
  }

  roots.forEach((node) => {
    if ((state.get(node.id) || 0) === 0) {
      visit(node.id);
    }
  });

  nodeOrder.forEach((node) => {
    if ((state.get(node.id) || 0) === 0) {
      visit(node.id);
    }
  });

  return edges;
}

function computeNodeLevels(nodes, edges) {
  const flowEdges = edges.filter((edge) => !edge.isLoop);
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const parents = new Map(nodes.map((node) => [node.id, new Set()]));
  const children = new Map(nodes.map((node) => [node.id, new Set()]));
  const inDegree = new Map(nodes.map((node) => [node.id, 0]));

  for (const edge of flowEdges) {
    parents.get(edge.target).add(edge.source);
    children.get(edge.source).add(edge.target);
    inDegree.set(edge.target, inDegree.get(edge.target) + 1);
  }

  const queue = nodes
    .filter((node) => inDegree.get(node.id) === 0)
    .sort((a, b) => a.sourceIndex - b.sourceIndex)
    .map((node) => node.id);

  const level = new Map(nodes.map((node) => [node.id, 0]));
  const topoOrder = [];

  while (queue.length > 0) {
    const nodeId = queue.shift();
    topoOrder.push(nodeId);

    for (const childId of children.get(nodeId)) {
      level.set(childId, Math.max(level.get(childId), level.get(nodeId) + 1));
      inDegree.set(childId, inDegree.get(childId) - 1);
      if (inDegree.get(childId) === 0) {
        queue.push(childId);
        queue.sort((leftId, rightId) => nodeById.get(leftId).sourceIndex - nodeById.get(rightId).sourceIndex);
      }
    }
  }

  nodes.forEach((node) => {
    if (!topoOrder.includes(node.id)) {
      level.set(node.id, level.get(node.id) ?? 0);
    }
  });

  return level;
}

function buildLevelPositions(nodes, nodeLevel, flowEdges, loopCount, corridorCount = 0) {
  const levelMembers = new Map();
  let maxLevel = 0;

  for (const node of nodes) {
    const level = nodeLevel.get(node.id) ?? 0;
    maxLevel = Math.max(maxLevel, level);
    if (!levelMembers.has(level)) {
      levelMembers.set(level, []);
    }
    levelMembers.get(level).push(node);
  }

  const levelCount = maxLevel + 1;
  const columnWidth = 420;
  const leftPadding = 180;
  const topPadding = 240 + Math.max(0, loopCount - 1) * 28;
  const corridorGap = 34;
  const bottomPadding = Math.max(160, corridorCount * corridorGap + 60);
  const rowGap = 150;
  const maxNodesInLevel = Math.max(...Array.from(levelMembers.values()).map((members) => members.length), 1);
  const width = Math.max(2400, leftPadding * 2 + levelCount * columnWidth);
  const height = Math.max(1200, topPadding + bottomPadding + 90 + Math.max(0, maxNodesInLevel - 1) * rowGap);
  const levelGap = levelCount > 1 ? (width - leftPadding * 2) / (levelCount - 1) : 0;
  const levelHeight = height - topPadding - bottomPadding;

  const levels = Array.from({ length: levelCount }, (_, level) => ({
    id: `level-${level}`,
    title: `Level ${level}`,
    x: leftPadding + level * levelGap,
    y: topPadding,
    width: 220,
    height: levelHeight,
    index: level,
  }));

  levels.forEach((level, index) => {
    level.leftGutter = index === 0
      ? level.x - columnWidth * 0.42
      : (levels[index - 1].x + level.x) / 2;
    level.rightGutter = index === levels.length - 1
      ? level.x + columnWidth * 0.42
      : (level.x + levels[index + 1].x) / 2;
  });

  const parentMap = new Map(nodes.map((node) => [node.id, []]));
  const childMap = new Map(nodes.map((node) => [node.id, []]));
  flowEdges.forEach((edge) => {
    parentMap.get(edge.target).push(edge.source);
    childMap.get(edge.source).push(edge.target);
  });

  const orderByLevel = new Map();
  levels.forEach((level) => {
    const members = (levelMembers.get(level.index) || []).slice().sort((a, b) => {
      return a.sourceIndex - b.sourceIndex || a.label.localeCompare(b.label);
    });
    orderByLevel.set(level.index, members);
  });

  const getOrderIndexMap = () => {
    const orderIndex = new Map();
    orderByLevel.forEach((members) => {
      members.forEach((node, index) => {
        orderIndex.set(node.id, index);
      });
    });
    return orderIndex;
  };

  const barycenter = (ids, orderIndex) => {
    if (!ids || ids.length === 0) {
      return Number.POSITIVE_INFINITY;
    }
    return ids.reduce((sum, id) => sum + (orderIndex.get(id) ?? 0), 0) / ids.length;
  };

  for (let pass = 0; pass < 6; pass += 1) {
    let orderIndex = getOrderIndexMap();
    for (let levelIndex = 1; levelIndex < levels.length; levelIndex += 1) {
      const members = orderByLevel.get(levelIndex);
      members.sort((left, right) => {
        const leftValue = barycenter(parentMap.get(left.id), orderIndex);
        const rightValue = barycenter(parentMap.get(right.id), orderIndex);
        if (leftValue !== rightValue) {
          return leftValue - rightValue;
        }
        return left.sourceIndex - right.sourceIndex;
      });
    }

    orderIndex = getOrderIndexMap();
    for (let levelIndex = levels.length - 2; levelIndex >= 0; levelIndex -= 1) {
      const members = orderByLevel.get(levelIndex);
      members.sort((left, right) => {
        const leftValue = barycenter(childMap.get(left.id), orderIndex);
        const rightValue = barycenter(childMap.get(right.id), orderIndex);
        if (leftValue !== rightValue) {
          return leftValue - rightValue;
        }
        return left.sourceIndex - right.sourceIndex;
      });
    }
  }

  for (const level of levels) {
    const members = orderByLevel.get(level.index) || [];
    const blockHeight = Math.max(0, (members.length - 1) * rowGap);
    const startY = level.y + 62 + Math.max(0, (levelHeight - 124 - blockHeight) / 2);
    members.forEach((node, index) => {
      node.level = level.index;
      node.levelId = level.id;
      node.levelTitle = level.title;
      node.rowIndex = index;
      node.anchorX = level.x;
      node.anchorY = startY + index * rowGap;
    });
  }

  return {
    levels,
    width,
    height,
    routing: {
      rowGap,
      topLoopY: topPadding - 68,
      loopGap: 20,
      corridorBaseY: height - bottomPadding + 30,
      corridorGap,
    },
  };
}

function buildState(parsed) {
  const nodeById = new Map();
  const classifiedEdges = classifyEdges(parsed.nodes, parsed.edges);
  const flowEdges = classifiedEdges.filter((edge) => !edge.isLoop);
  const loopEdges = classifiedEdges.filter((edge) => edge.isLoop);
  loopEdges
    .sort((left, right) => {
      if (left.source === right.source) {
        return left.target.localeCompare(right.target);
      }
      return left.source.localeCompare(right.source);
    })
    .forEach((edge, index) => {
      edge.loopIndex = index;
    });
  const nodeLevel = computeNodeLevels(parsed.nodes, classifiedEdges);

  // Count corridor edges (backward + long forward) so buildLevelPositions
  // can reserve enough bottom padding for their lanes.
  const corridorEdgeCount = classifiedEdges.filter((e) => {
    if (e.isLoop) return false;
    const sl = nodeLevel.get(e.source) ?? 0;
    const tl = nodeLevel.get(e.target) ?? 0;
    return tl < sl || (tl - sl) >= 2;
  }).length;

  const nodes = parsed.nodes.map((node) => {
    const dims = node.shape === "join"
      ? { width: 24, height: 24, radius: 11 }
      : { width: Math.max(126, node.label.length * 7 + 28), height: 40, radius: 14 };

    const enriched = {
      ...node,
      ...dims,
      x: 0,
      y: 0,
      anchorX: 0,
      anchorY: 0,
      edges: [],
      neighbors: new Set(),
      element: null,
      textElement: null,
    };
    nodeById.set(node.id, enriched);
    return enriched;
  });

  const { levels, width, height, routing } = buildLevelPositions(nodes, nodeLevel, flowEdges, loopEdges.length, corridorEdgeCount);
  nodes.forEach((node) => {
    node.x = node.anchorX;
    node.y = node.anchorY;
  });

  const edges = classifiedEdges.map((edge, index) => {
    const enriched = {
      ...edge,
      id: `edge-${index}`,
      sourceNode: nodeById.get(edge.source),
      targetNode: nodeById.get(edge.target),
      sourcePortY: 0,
      targetPortY: 0,
      corridorLane: null,
      element: null,
    };
    enriched.sourceNode.edges.push(enriched);
    enriched.targetNode.edges.push(enriched);
    enriched.sourceNode.neighbors.add(enriched.targetNode.id);
    enriched.targetNode.neighbors.add(enriched.sourceNode.id);
    return enriched;
  });

  // Spread edges across source/target ports so parallel edges don't overlap.
  const PORT_SPREAD = 12;
  const edgesBySource = new Map();
  const edgesByTarget = new Map();
  for (const edge of edges) {
    if (!edgesBySource.has(edge.source)) edgesBySource.set(edge.source, []);
    edgesBySource.get(edge.source).push(edge);
    if (!edgesByTarget.has(edge.target)) edgesByTarget.set(edge.target, []);
    edgesByTarget.get(edge.target).push(edge);
  }
  for (const group of edgesBySource.values()) {
    group.sort((a, b) => (a.targetNode.y ?? 0) - (b.targetNode.y ?? 0));
    const n = group.length;
    const halfH = (nodeById.get(group[0].source)?.height ?? 40) / 2 - 4;
    const spread = Math.min(PORT_SPREAD, n > 1 ? (halfH * 2) / (n - 1) : PORT_SPREAD);
    group.forEach((edge, i) => {
      edge.sourcePortY = n > 1 ? (i - (n - 1) / 2) * spread : 0;
    });
  }
  for (const group of edgesByTarget.values()) {
    group.sort((a, b) => (a.sourceNode.y ?? 0) - (b.sourceNode.y ?? 0));
    const n = group.length;
    const halfH = (nodeById.get(group[0].target)?.height ?? 40) / 2 - 4;
    const spread = Math.min(PORT_SPREAD, n > 1 ? (halfH * 2) / (n - 1) : PORT_SPREAD);
    group.forEach((edge, i) => {
      edge.targetPortY = n > 1 ? (i - (n - 1) / 2) * spread : 0;
    });
  }

  // Assign bottom-corridor lanes to backward and long forward edges.
  // Shorter level-span edges get inner lanes (closer to nodes); longer get outer.
  const corridorEdges = edges.filter((e) => {
    if (e.isLoop) return false;
    const sl = e.sourceNode.level ?? 0;
    const tl = e.targetNode.level ?? 0;
    return tl < sl || (tl - sl) >= 2;
  });
  corridorEdges
    .sort((a, b) => {
      const spanA = Math.abs((a.targetNode.level ?? 0) - (a.sourceNode.level ?? 0));
      const spanB = Math.abs((b.targetNode.level ?? 0) - (b.sourceNode.level ?? 0));
      return spanA - spanB;
    })
    .forEach((edge, i) => { edge.corridorLane = i; });

  return { width, height, nodes, edges, nodeById, levels, routing };
}

function clearLayers() {
  edgeLayer.replaceChildren();
  nodeLayer.replaceChildren();
  edgeHitLayer.replaceChildren();
}

function createSvgElement(name, attributes = {}) {
  const element = document.createElementNS(SVG_NS, name);
  for (const [key, value] of Object.entries(attributes)) {
    element.setAttribute(key, value);
  }
  return element;
}

function wrapLabel(label, maxCharsPerLine) {
  if (!label) {
    return [""];
  }

  const words = label.split(/\s+/);
  const lines = [];
  let current = words[0];

  for (let i = 1; i < words.length; i += 1) {
    const candidate = `${current} ${words[i]}`;
    if (candidate.length <= maxCharsPerLine) {
      current = candidate;
    } else {
      lines.push(current);
      current = words[i];
    }
  }

  lines.push(current);
  return lines;
}

function getNodeConnectionPoint(node, direction, yOffset = 0) {
  if (node.shape === "join") {
    return {
      x: node.x + direction * node.radius,
      y: node.y + yOffset,
    };
  }

  return {
    x: node.x + direction * (node.width / 2),
    y: node.y + yOffset,
  };
}

// Returns a connection point on the node border closest to (targetX, targetY).
// For steep angles (more vertical than horizontal) it picks top/bottom centre;
// for shallow angles it picks left/right centre. portOffset spreads parallel
// edges: applied to Y for horizontal exits, to X for vertical exits.
function getSmartConnectionPoint(node, targetX, targetY, portOffset = 0) {
  const dx = targetX - node.x;
  const dy = targetY - node.y;
  const isVertical = Math.abs(dy) > Math.abs(dx) * 0.8;

  if (node.shape === "join") {
    const r = node.radius;
    if (isVertical) return { x: node.x + portOffset, y: node.y + (dy >= 0 ? r : -r) };
    return { x: node.x + (dx >= 0 ? r : -r), y: node.y + portOffset };
  }

  if (isVertical) {
    return { x: node.x + portOffset, y: node.y + (dy >= 0 ? node.height / 2 : -node.height / 2) };
  }
  return { x: node.x + (dx >= 0 ? node.width / 2 : -node.width / 2), y: node.y + portOffset };
}

function getNodeTopPoint(node, xOffset = 0) {
  const halfH = node.shape === "join" ? node.radius : node.height / 2;
  return { x: node.x + xOffset, y: node.y - halfH };
}

function getNodeBottomPoint(node, xOffset = 0) {
  const halfH = node.shape === "join" ? node.radius : node.height / 2;
  return { x: node.x + xOffset, y: node.y + halfH };
}

function offsetPoint(from, to, distance) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const length = Math.hypot(dx, dy) || 1;
  return {
    x: from.x + (dx / length) * distance,
    y: from.y + (dy / length) * distance,
  };
}

function buildRoundedPath(points, radius = 14) {
  const filtered = points.filter((point, index) => {
    if (index === 0) {
      return true;
    }
    const previous = points[index - 1];
    return previous.x !== point.x || previous.y !== point.y;
  });

  if (filtered.length <= 1) {
    return "";
  }

  let path = `M ${filtered[0].x} ${filtered[0].y}`;

  for (let index = 1; index < filtered.length - 1; index += 1) {
    const previous = filtered[index - 1];
    const current = filtered[index];
    const next = filtered[index + 1];
    const inLength = Math.hypot(current.x - previous.x, current.y - previous.y);
    const outLength = Math.hypot(next.x - current.x, next.y - current.y);
    const cornerRadius = Math.min(radius, inLength / 2, outLength / 2);

    if (cornerRadius < 1) {
      path += ` L ${current.x} ${current.y}`;
      continue;
    }

    const entry = offsetPoint(current, previous, cornerRadius);
    const exit = offsetPoint(current, next, cornerRadius);
    path += ` L ${entry.x} ${entry.y}`;
    path += ` Q ${current.x} ${current.y} ${exit.x} ${exit.y}`;
  }

  const last = filtered[filtered.length - 1];
  path += ` L ${last.x} ${last.y}`;
  return path;
}

function buildEdgePath(edge) {
  const sourceLevel = edge.sourceNode.level ?? 0;
  const targetLevel = edge.targetNode.level ?? 0;
  const isBackward = !edge.isLoop && targetLevel < sourceLevel;
  const levelSpan = Math.abs(targetLevel - sourceLevel);

  // ── Loop edges: top-centre arc above the node band ───────────────────────
  if (edge.isLoop) {
    const sourcePoint = getNodeTopPoint(edge.sourceNode, edge.sourcePortY ?? 0);
    const targetPoint = getNodeTopPoint(edge.targetNode, edge.targetPortY ?? 0);
    const dx = targetPoint.x - sourcePoint.x;
    const dy = targetPoint.y - sourcePoint.y;
    const lift = Math.max(90, 40 + Math.abs(dx) * 0.14 + Math.abs(dy) * 0.12 + (edge.loopIndex ?? 0) * 28);
    return `M ${sourcePoint.x} ${sourcePoint.y} C ${sourcePoint.x} ${sourcePoint.y - lift}, ${targetPoint.x} ${targetPoint.y - lift}, ${targetPoint.x} ${targetPoint.y}`;
  }

  // ── Corridor edges: orthogonal routing through a lane below the node band ─
  // Backward edges and forward edges spanning 2+ levels are routed here so
  // they never pass through intermediate nodes.
  if (edge.corridorLane !== null) {
    // Corridor edges route below the node band — connect from/to bottom centre.
    // sourcePortY/targetPortY are reused as X offsets to spread parallel edges.
    const sp = getNodeBottomPoint(edge.sourceNode, edge.sourcePortY ?? 0);
    const tp = getNodeBottomPoint(edge.targetNode, edge.targetPortY ?? 0);
    const laneY = graphState.routing.corridorBaseY + (edge.corridorLane ?? 0) * graphState.routing.corridorGap;
    return `M ${sp.x} ${sp.y} C ${sp.x} ${laneY}, ${tp.x} ${laneY}, ${tp.x} ${tp.y}`;
  }

  // ── Short forward edge: bezier with smart top/bottom or left/right ports ──
  const sourcePoint = getSmartConnectionPoint(
    edge.sourceNode, edge.targetNode.x, edge.targetNode.y, edge.sourcePortY ?? 0
  );
  const targetPoint = getSmartConnectionPoint(
    edge.targetNode, edge.sourceNode.x, edge.sourceNode.y, edge.targetPortY ?? 0
  );
  const dx = targetPoint.x - sourcePoint.x;
  const dy = targetPoint.y - sourcePoint.y;
  const absDx = Math.abs(dx);
  const absDy = Math.abs(dy);

  if (absDy > absDx * 0.8) {
    // Vertical-dominant: bezier pulls along Y axis
    const signY = dy >= 0 ? 1 : -1;
    const ctrl = absDy * 0.44;
    return `M ${sourcePoint.x} ${sourcePoint.y} C ${sourcePoint.x} ${sourcePoint.y + signY * ctrl}, ${targetPoint.x} ${targetPoint.y - signY * ctrl}, ${targetPoint.x} ${targetPoint.y}`;
  }

  const ctrl = absDx * Math.min(0.44, 0.3 + levelSpan * 0.04);
  return `M ${sourcePoint.x} ${sourcePoint.y} C ${sourcePoint.x + ctrl} ${sourcePoint.y}, ${targetPoint.x - ctrl} ${targetPoint.y}, ${targetPoint.x} ${targetPoint.y}`;
}

function updateGeometry() {
  for (const edge of graphState.edges) {
    const d = buildEdgePath(edge);
    edge.element.setAttribute("d", d);
    if (edge.hitElement) edge.hitElement.setAttribute("d", d);
  }

  for (const node of graphState.nodes) {
    node.element.setAttribute("transform", `translate(${node.x} ${node.y})`);
  }
}

function renderGraph() {
  clearLayers();

  for (const edge of graphState.edges) {
    const sourceLevel = edge.sourceNode?.level ?? 0;
    const targetLevel = edge.targetNode?.level ?? 0;
    const isBackward = !edge.isLoop && targetLevel < sourceLevel;
    const markerEnd = edge.isLoop ? "url(#arrow-loop)" : isBackward ? "url(#arrow-back)" : "url(#arrow-fwd)";
    const markerActive = edge.isLoop ? "url(#arrow-loop-active)" : isBackward ? "url(#arrow-back-active)" : "url(#arrow-fwd-active)";

    const attrs = {
      class: edge.isLoop
        ? edge.dashed ? "edge loop dashed" : "edge loop"
        : edge.dashed ? "edge dashed" : "edge",
      fill: "none",
      "marker-end": markerEnd,
    };
    const path = createSvgElement("path", attrs);
    edge.markerDefault = markerEnd;
    edge.markerActive = markerActive;
    // Invisible wide path on top to make clicking thin curves easier.
    // Must carry the "edge" class so isGraphObject() recognises it and
    // prevents the SVG-level click handler from clearing the selection.
    const hitPath = createSvgElement("path", {
      class: "edge",
      fill: "none",
      stroke: "rgba(0,0,0,0.001)",
      "stroke-width": "40",
      style: "cursor: pointer; pointer-events: stroke",
    });
    edge.element = path;
    edge.hitElement = hitPath;

    const handleEdgeClick = (event) => {
      event.stopPropagation();
      if (selectedEdgeId === edge.id) {
        selectedEdgeId = null;
      } else {
        selectedEdgeId = edge.id;
      }
      selectedNodeId = null;
      updateSelection();
    };
    path.addEventListener("click", handleEdgeClick);
    hitPath.addEventListener("click", handleEdgeClick);

    const edgeTooltip = [
      `${edge.sourceNode.label} → ${edge.targetNode.label}`,
      edge.description,
    ].filter(Boolean).join("\n");
    hitPath.addEventListener("mouseenter", (e) => showTooltip(edgeTooltip, e.clientX, e.clientY));
    hitPath.addEventListener("mousemove", (e) => positionTooltip(e.clientX, e.clientY));
    hitPath.addEventListener("mouseleave", hideTooltip);

    edgeLayer.appendChild(path);
    edgeHitLayer.appendChild(hitPath);
  }

  for (const node of graphState.nodes) {
    const group = createSvgElement("g", {
      class: "node",
      "data-node-id": node.id,
    });

    let shape;
    if (node.shape === "join") {
      shape = createSvgElement("circle", {
        class: "node-shape",
        r: node.radius,
        cx: 0,
        cy: 0,
        fill: node.fill,
        stroke: node.stroke,
      });
    } else {
      shape = createSvgElement("rect", {
        class: "node-shape",
        x: -node.width / 2,
        y: -node.height / 2,
        width: node.width,
        height: node.height,
        rx: node.radius,
        ry: node.radius,
        fill: node.fill,
        stroke: node.stroke,
      });
    }

    const text = createSvgElement("text", {
      class: "node-label",
    });

    const lines = wrapLabel(node.label, node.shape === "join" ? 1 : 18);
    const lineHeight = 15;
    const startOffset = ((lines.length - 1) * lineHeight) / -2;
    lines.forEach((line, index) => {
      const tspan = createSvgElement("tspan", {
        x: 0,
        y: startOffset + index * lineHeight,
      });
      tspan.textContent = line;
      text.appendChild(tspan);
    });

    group.appendChild(shape);
    group.appendChild(text);
    node.element = group;
    node.textElement = text;

    group.addEventListener("click", (event) => {
      event.stopPropagation();
      if (selectedNodeId === node.id) {
        selectedNodeId = null;
      } else {
        selectedNodeId = node.id;
      }
      selectedEdgeId = null;
      updateSelection();
    });

    if (node.description) {
      group.addEventListener("mouseenter", (e) => showTooltip(node.description, e.clientX, e.clientY));
      group.addEventListener("mousemove", (e) => positionTooltip(e.clientX, e.clientY));
      group.addEventListener("mouseleave", hideTooltip);
    }

    nodeLayer.appendChild(group);
  }

  updateGeometry();
  updateSelection();
  applyViewTransform();
}

function updateSelectionPanelEdge(edge) {
  const src = edge.sourceNode;
  const tgt = edge.targetNode;
  selectionMeta.innerHTML = `
    <div><strong>Edge:</strong> ${src.label || src.id} → ${tgt.label || tgt.id}</div>
    <div><strong>Type:</strong> ${edge.isLoop ? "loop" : edge.dashed ? "dependency" : "flow"}</div>
  `;
  neighborList.replaceChildren();
  [src, tgt].forEach((node) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip";
    chip.innerHTML = `<span class="chip-dot ${node.className || "assistant"}"></span>${node.label || node.id}`;
    chip.addEventListener("click", () => {
      selectedNodeId = node.id;
      selectedEdgeId = null;
      updateSelection();
      panToNode(node);
    });
    if (node.description) {
      chip.addEventListener("mouseenter", (e) => showTooltip(node.description, e.clientX, e.clientY));
      chip.addEventListener("mousemove", (e) => positionTooltip(e.clientX, e.clientY));
      chip.addEventListener("mouseleave", hideTooltip);
    }
    neighborList.appendChild(chip);
  });
}

function updateSelectionPanel(node) {
  if (!node) {
    selectionMeta.innerHTML = "<div><strong>Node:</strong> none</div><div><strong>Direct connections:</strong> 0</div>";
    neighborList.replaceChildren();
    return;
  }

  const neighbors = Array.from(node.neighbors)
    .map((id) => graphState.nodeById.get(id))
    .sort((a, b) => a.label.localeCompare(b.label));

  selectionMeta.innerHTML = `
    <div><strong>Node:</strong> ${node.label || node.id}</div>
    <div><strong>Internal id:</strong> ${node.id}</div>
    <div><strong>Level:</strong> ${node.levelTitle}</div>
    <div><strong>Direct connections:</strong> ${neighbors.length}</div>
  `;

  neighborList.replaceChildren();
  neighbors.forEach((neighbor) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip";
    chip.innerHTML = `<span class="chip-dot ${neighbor.className || "assistant"}"></span>${neighbor.label || neighbor.id}`;
    chip.addEventListener("click", () => {
      selectedNodeId = neighbor.id;
      updateSelection();
      panToNode(neighbor);
    });
    if (neighbor.description) {
      chip.addEventListener("mouseenter", (e) => showTooltip(neighbor.description, e.clientX, e.clientY));
      chip.addEventListener("mousemove", (e) => positionTooltip(e.clientX, e.clientY));
      chip.addEventListener("mouseleave", hideTooltip);
    }
    neighborList.appendChild(chip);
  });
}

function updateSelection() {
  const selectedNode = selectedNodeId ? graphState.nodeById.get(selectedNodeId) : null;
  const selectedEdge = selectedEdgeId ? graphState.edges.find((edge) => edge.id === selectedEdgeId) : null;
  const activeIds = new Set();
  const activeEdgeIds = new Set();
  const isJoinNode = (node) => node && node.shape === "join";

  if (selectedEdge) {
    activeEdgeIds.add(selectedEdge.id);
    activeIds.add(selectedEdge.sourceNode.id);
    activeIds.add(selectedEdge.targetNode.id);
  } else if (selectedNode) {
    activeIds.add(selectedNode.id);
    for (const edge of selectedNode.edges) {
      activeEdgeIds.add(edge.id);
      activeIds.add(edge.sourceNode.id);
      activeIds.add(edge.targetNode.id);

      const adjacentJoin = edge.sourceNode.id === selectedNode.id ? edge.targetNode : edge.sourceNode;
      if (!isJoinNode(adjacentJoin)) {
        continue;
      }

      for (const joinEdge of adjacentJoin.edges) {
        activeEdgeIds.add(joinEdge.id);
        activeIds.add(joinEdge.sourceNode.id);
        activeIds.add(joinEdge.targetNode.id);
      }
    }
  }

  const hasSelection = Boolean(selectedNode || selectedEdge);

  for (const node of graphState.nodes) {
    node.element.classList.toggle("active", hasSelection && activeIds.has(node.id));
    node.element.classList.toggle("faded", hasSelection && !activeIds.has(node.id));
  }

  for (const edge of graphState.edges) {
    const isActive = activeEdgeIds.has(edge.id);
    edge.element.classList.toggle("active", isActive);
    edge.element.classList.toggle("faded", hasSelection && !isActive);
    if (edge.markerDefault) {
      edge.element.setAttribute("marker-end", isActive ? edge.markerActive : edge.markerDefault);
    }
  }

  if (selectedEdge) {
    updateSelectionPanelEdge(selectedEdge);
  } else {
    updateSelectionPanel(selectedNode);
  }
}

function applyViewTransform() {
  viewport.setAttribute(
    "transform",
    `matrix(${viewState.scale} 0 0 ${viewState.scale} ${viewState.x} ${viewState.y})`
  );
}

function panToNode(node, duration = 420) {
  const { box } = getViewBoxMetrics();
  const targetX = box.width / 2 - node.x * viewState.scale;
  const targetY = box.height / 2 - node.y * viewState.scale;
  const startX = viewState.x;
  const startY = viewState.y;
  const startTime = performance.now();

  function ease(t) {
    return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t;
  }

  function step(now) {
    const t = Math.min((now - startTime) / duration, 1);
    const e = ease(t);
    viewState.x = startX + (targetX - startX) * e;
    viewState.y = startY + (targetY - startY) * e;
    applyViewTransform();
    if (t < 1) requestAnimationFrame(step);
  }

  requestAnimationFrame(step);
}

function fitGraph() {
  if (!graphState || graphState.nodes.length === 0) {
    return;
  }

  let minX = Math.min(...graphState.levels.map((level) => level.leftGutter)) - 40;
  let maxX = Math.max(...graphState.levels.map((level) => level.rightGutter)) + 40;
  let minY = Infinity;
  let maxY = -Infinity;

  for (const node of graphState.nodes) {
    const halfWidth = node.shape === "join" ? node.radius : node.width / 2;
    const halfHeight = node.shape === "join" ? node.radius : node.height / 2;
    minX = Math.min(minX, node.x - halfWidth);
    maxX = Math.max(maxX, node.x + halfWidth);
    minY = Math.min(minY, node.y - halfHeight);
    maxY = Math.max(maxY, node.y + halfHeight);
  }

  const loopCount = graphState.edges.filter((edge) => edge.isLoop).length;
  minY -= Math.max(140, loopCount * 16 + 70);

  const { box } = getViewBoxMetrics();
  const graphWidth = maxX - minX;
  const graphHeight = maxY - minY;
  const scale = Math.min(
    (box.width * 0.88) / Math.max(graphWidth, 1),
    (box.height * 0.88) / Math.max(graphHeight, 1),
    1.35
  );

  viewState.scale = scale;
  viewState.x = box.width / 2 - ((minX + maxX) / 2) * scale;
  viewState.y = box.height / 2 - ((minY + maxY) / 2) * scale;
  applyViewTransform();
}

function rerender() {
  selectedNodeId = null;
  selectedEdgeId = null;
  graphState = buildState(parseMermaid(sourceInput.value));
  svg.setAttribute("viewBox", `0 0 ${graphState.width} ${graphState.height}`);
  renderGraph();
  window.setTimeout(fitGraph, 140);
}

function attachCanvasInteractions() {
  const isGraphObject = (target) => {
    return target instanceof Element && Boolean(target.closest(".node, .edge"));
  };

  svg.addEventListener("pointerdown", (event) => {
    // Panning requires Cmd (Mac) or Ctrl (other platforms).
    // When Cmd is held, panning starts regardless of what was clicked —
    // this lets the user pan while a node or edge is selected.
    if (!event.metaKey && !event.ctrlKey) {
      if (isGraphObject(event.target)) {
        return;
      }
      return;
    }

    event.preventDefault();
    const point = pointerToSvg(event.clientX, event.clientY);
    panState = {
      pointerId: event.pointerId,
      startX: point.x,
      startY: point.y,
      originX: viewState.x,
      originY: viewState.y,
      moved: false,
    };
    canvasBg.classList.add("dragging");
    svg.setPointerCapture(event.pointerId);
  });

  svg.addEventListener("pointermove", (event) => {
    if (panState) {
      const point = pointerToSvg(event.clientX, event.clientY);
      viewState.x = panState.originX + (point.x - panState.startX);
      viewState.y = panState.originY + (point.y - panState.startY);
      panState.moved = true;
      applyViewTransform();
    }
  });

  let panMoved = false;

  svg.addEventListener("pointerup", (event) => {
    if (panState && panState.pointerId === event.pointerId) {
      panMoved = panState.moved;
      panState = null;
      canvasBg.classList.remove("dragging");
    }
  });

  svg.addEventListener("pointerleave", () => {
    if (panState) {
      panMoved = panState.moved;
      panState = null;
      canvasBg.classList.remove("dragging");
    }
  });

  svg.addEventListener("click", (event) => {
    // If this click is the tail end of a pan gesture, don't clear the selection.
    if (panMoved) {
      panMoved = false;
      return;
    }
    if (isGraphObject(event.target)) {
      return;
    }

    selectedNodeId = null;
    selectedEdgeId = null;
    updateSelection();
  });

  svg.addEventListener("wheel", (event) => {
    event.preventDefault();
    const point = pointerToSvg(event.clientX, event.clientY);
    const pointerX = point.x;
    const pointerY = point.y;
    const worldX = (pointerX - viewState.x) / viewState.scale;
    const worldY = (pointerY - viewState.y) / viewState.scale;
    const nextScale = Math.min(8, Math.max(0.35, viewState.scale * (event.deltaY < 0 ? 1.08 : 0.92)));

    viewState.x = pointerX - worldX * nextScale;
    viewState.y = pointerY - worldY * nextScale;
    viewState.scale = nextScale;
    applyViewTransform();
  }, { passive: false });
}

fitButton.addEventListener("click", fitGraph);
resetButton.addEventListener("click", () => {
  selectedNodeId = null;
  selectedEdgeId = null;
  updateSelection();
  fitGraph();
});
renderButton.addEventListener("click", rerender);
window.addEventListener("resize", () => {
  window.setTimeout(fitGraph, 80);
});

attachCanvasInteractions();

function extractMermaid(markdown) {
  const match = markdown.match(/```mermaid\r?\n([\s\S]*?)```/);
  return match ? match[1].trimEnd() : null;
}

// Load the Mermaid block from CLAUDE.md (one level up). Falls back to the
// hardcoded defaultSource if the file cannot be fetched (e.g. file:// origin).
// Polls every 2 seconds and rerenders automatically when the block changes.
let lastSource = null;

function loadFromClaude() {
  return fetch("../CLAUDE.md")
    .then((r) => {
      if (!r.ok) throw new Error(r.statusText);
      return r.text();
    })
    .then((markdown) => {
      const source = extractMermaid(markdown);
      if (!source) throw new Error("No mermaid block found in CLAUDE.md");
      if (source !== lastSource) {
        lastSource = source;
        sourceInput.value = source;
        rerender();
      }
    })
    .catch(() => {
      if (lastSource === null) {
        // First load failed — fall back to built-in default.
        rerender();
      }
    });
}

loadFromClaude().then(() => {
  setInterval(loadFromClaude, 2000);
});
