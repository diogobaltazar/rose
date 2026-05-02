import type { Task, TimerStatus, TimerStopResult, ListTasksParams, Session } from './types';

const BASE = '';

function qs(params: Record<string, string | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined) as [string, string][];
  if (entries.length === 0) return '';
  return '?' + new URLSearchParams(entries).toString();
}

export class TopgunClient {
  async listTasks(params?: ListTasksParams): Promise<Task[]> {
    const q = params ? qs({
      search: params.search,
      sort: params.sort,
      order: params.order,
      status: params.status,
    }) : '';
    const r = await fetch(`${BASE}/backlog${q}`);
    if (!r.ok) throw new Error(`listTasks: ${r.status}`);
    return r.json();
  }

  async refreshBacklog(): Promise<void> {
    await fetch(`${BASE}/backlog/refresh`, { method: 'POST' });
  }

  async closeTask(taskId: string): Promise<boolean> {
    const r = await fetch(`${BASE}/tasks/${encodeURIComponent(taskId)}/close`, { method: 'POST' });
    if (!r.ok) return false;
    const data = await r.json();
    return data.status === 'closed';
  }

  async timerStatus(): Promise<TimerStatus | null> {
    const r = await fetch(`${BASE}/timer/status`);
    if (!r.ok) throw new Error(`timerStatus: ${r.status}`);
    const data: TimerStatus = await r.json();
    if (!data.running && !data.task_id) return null;
    return data;
  }

  async timerStart(taskId: string, taskTitle: string = ''): Promise<void> {
    const r = await fetch(`${BASE}/timer/start`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ task_id: taskId, task_title: taskTitle }),
    });
    const data = await r.json();
    if (data.error) throw new Error(data.error);
  }

  async timerStop(): Promise<TimerStopResult> {
    const r = await fetch(`${BASE}/timer/stop`, { method: 'POST' });
    const data = await r.json();
    if (data.error) throw new Error(data.error);
    return data;
  }

  connectSessions(onData: (sessions: Session[]) => void): WebSocket {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${window.location.host}/ws`);
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (Array.isArray(data)) onData(data);
      } catch { /* ignore non-array messages */ }
    };
    return ws;
  }

  connectBacklog(onData: (items: Task[]) => void): WebSocket {
    const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${proto}//${window.location.host}/backlog/ws`);
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data);
        if (Array.isArray(data)) onData(data);
      } catch { /* ignore non-array messages */ }
    };
    return ws;
  }

  async calendarStatus(): Promise<Record<string, unknown>> {
    const r = await fetch(`${BASE}/calendar/status`);
    if (!r.ok) throw new Error(`calendarStatus: ${r.status}`);
    return r.json();
  }

  async calendarSync(): Promise<Record<string, unknown>> {
    const r = await fetch(`${BASE}/calendar/sync`, { method: 'POST' });
    if (!r.ok) throw new Error(`calendarSync: ${r.status}`);
    return r.json();
  }

  async calendarSchedule(): Promise<Record<string, unknown>> {
    const r = await fetch(`${BASE}/calendar/schedule`, { method: 'POST' });
    if (!r.ok) throw new Error(`calendarSchedule: ${r.status}`);
    return r.json();
  }

  async calendarSlots(duration: number = 60, after?: string): Promise<Array<{start: string; end: string}>> {
    const params = new URLSearchParams({ duration: String(duration) });
    if (after) params.set('after', after);
    const r = await fetch(`${BASE}/calendar/slots?${params}`);
    if (!r.ok) throw new Error(`calendarSlots: ${r.status}`);
    return r.json();
  }
}

export const client = new TopgunClient();
