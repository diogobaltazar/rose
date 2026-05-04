export interface AppConfig {
  auth0_domain: string;
  auth0_client_id: string;
  auth0_audience: string;
}

export interface Mission {
  id: string;
  source_type: "github" | "obsidian";
  source_repo: string | null;
  number: number | null;
  title: string;
  state: "open" | "closed";
  created_at: string | null;
  closed_at: string | null;
  priority: "high" | "medium" | "low" | null;
  labels: string[];
  about: string | null;
  motivation: string | null;
  acceptance_criteria: string[];
  dependencies: string[];
  url: string | null;
  file: string | null;
  line: number | null;
}

export interface Agent {
  agent_id: string;
  agent_type: string;
  description: string;
  started_at: string | null;
  ended_at: string | null;
  duration: number | null;
  tool_count: number;
  tokens: number;
  usd: number;
  status: "live" | "done";
  cwd: string | null;
}

export interface IntelDocument {
  uid: string;
  source: "github" | "obsidian";
  source_url: string;
  title?: string;
  labels?: string[];
  auto_discovered?: boolean;
}

export interface IntelStats {
  total: number;
  by_source: { github: number; obsidian: number };
  missions: number;
  drafts: number;
  ready: number;
}

export interface IntelSearchResult {
  uid: string;
  source: "github" | "obsidian";
  source_url: string;
  title: string;
}

export interface IntelTimerStatus {
  uid: string;
  status: "running" | "stopped";
  current_start: string | null;
  entries: { start: string; end: string; elapsed_s: number }[];
  total_s: number;
}

export interface Engagement {
  session_id: string;
  status: "live" | "done";
  started_at: string | null;
  title: string | null;
  branch: string | null;
  project: string;
  duration: number | null;
  total_tools: number;
  total_tokens: number;
  total_usd: number;
  own_kb: number | null;
  agents: Agent[];
}
