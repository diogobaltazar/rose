export interface Task {
  id: string;
  source_type: string;
  source_repo: string | null;
  source_description: string;
  number: number | null;
  title: string;
  state: string;
  created_at: string | null;
  closed_at: string | null;
  priority: string | null;
  best_before: string | null;
  must_before: string | null;
  about: string | null;
  motivation: string | null;
  acceptance_criteria: string[];
  dependencies: string[];
  url: string | null;
  file: string | null;
  line: number | null;
}

export interface TimerStatus {
  running: boolean;
  task_id?: string;
  task_title?: string;
  started_at?: string;
  elapsed_s?: number;
}

export interface TimerStopResult {
  task_id: string;
  task_title: string;
  started_at: string;
  stopped_at: string;
  elapsed_s: number;
}

export interface ListTasksParams {
  search?: string;
  sort?: string;
  order?: 'asc' | 'desc';
  status?: string;
}

export interface Session {
  session_id: string;
  process_sid: string | null;
  pid: number | null;
  status: 'live' | 'done';
  project: string;
  branch: string | null;
  started_at: string | null;
  title: string | null;
  duration: number | null;
  total_kb: number | null;
  total_tools: number;
  total_tokens: number;
  total_usd: number;
  own_kb: number | null;
  own_tools: number;
  own_tokens: number;
  own_usd: number;
  own_duration: number | null;
  agents: Agent[];
  team_config: unknown;
  meta: Record<string, unknown>;
}

export interface Agent {
  agent_id: string;
  agent_type: string;
  description: string;
  started_at: string | null;
  ended_at: string | null;
  size_kb: number | null;
  tool_count: number;
  tokens: number;
  usd: number;
  duration: number | null;
  status: 'live' | 'done';
  cwd: string | null;
}
