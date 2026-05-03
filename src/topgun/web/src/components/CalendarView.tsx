import { useState, useEffect } from 'react';
import { COLORS, fmtDuration } from './constants';
import { client } from '../sdk/client';

interface ScheduledEvent {
  task_id: string;
  title: string;
  start: string;
  end: string;
}

interface CalendarStatus {
  connected: boolean;
  calendar_name: string;
  scheduled_events: number;
  sync_token: string | null;
  events: Record<string, {
    scheduled_start: string;
    scheduled_end: string;
    user_modified: boolean;
  }>;
}

function fmtSlot(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleString('en-GB', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false });
  } catch { return iso.slice(0, 16); }
}

export function CalendarView() {
  const [status, setStatus] = useState<CalendarStatus | null>(null);
  const [scheduling, setScheduling] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [lastResult, setLastResult] = useState<{ scheduled: ScheduledEvent[]; unschedulable: Array<{ title: string; reason: string }> } | null>(null);

  useEffect(() => {
    loadStatus();
  }, []);

  async function loadStatus() {
    try {
      const s = await client.calendarStatus() as unknown as CalendarStatus;
      setStatus(s);
    } catch { /* ignore */ }
  }

  async function handleSchedule() {
    setScheduling(true);
    try {
      const result = await client.calendarSchedule() as unknown as { scheduled: ScheduledEvent[]; unschedulable: Array<{ title: string; reason: string }> };
      setLastResult(result);
      await loadStatus();
    } catch { /* ignore */ }
    setScheduling(false);
  }

  async function handleSync() {
    setSyncing(true);
    try {
      await client.calendarSync();
      await loadStatus();
    } catch { /* ignore */ }
    setSyncing(false);
  }

  const events = status?.events || {};
  const eventList = Object.entries(events);

  return (
    <div className="backlog-view">
      <div className="backlog-toolbar">
        <span className="backlog-view-title">calendar</span>
        <span style={{ color: status?.connected ? COLORS.neon : COLORS.dim, fontSize: 11 }}>
          {status?.connected ? `● ${status.calendar_name}` : '○ not connected'}
        </span>
        <span className="bl-sync-time">{status?.scheduled_events ?? 0} events</span>
        <button className={`bl-refresh-btn${syncing ? ' refreshing' : ''}`} onClick={handleSync} disabled={syncing}>
          {syncing ? '↻ …' : '↻ sync'}
        </button>
        <button className={`bl-refresh-btn${scheduling ? ' refreshing' : ''}`} onClick={handleSchedule} disabled={scheduling}>
          {scheduling ? '⏳ …' : '📅 schedule'}
        </button>
      </div>

      {lastResult && lastResult.scheduled.length > 0 && (
        <div style={{ padding: '12px 24px', borderBottom: `1px solid var(--border)` }}>
          <div style={{ fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: COLORS.neon, marginBottom: 8 }}>
            just scheduled
          </div>
          {lastResult.scheduled.map((ev, i) => (
            <div key={i} style={{ fontSize: 12, color: COLORS.pearl, marginBottom: 4 }}>
              <span style={{ color: COLORS.neon }}>●</span>{' '}
              {ev.title}{' '}
              <span style={{ color: COLORS.dim }}>{fmtSlot(ev.start)} – {fmtSlot(ev.end)}</span>
            </div>
          ))}
        </div>
      )}

      {lastResult && lastResult.unschedulable.length > 0 && (
        <div style={{ padding: '12px 24px', borderBottom: `1px solid var(--border)` }}>
          <div style={{ fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase', color: COLORS.usd, marginBottom: 8 }}>
            unschedulable
          </div>
          {lastResult.unschedulable.map((u, i) => (
            <div key={i} style={{ fontSize: 12, color: COLORS.dim, marginBottom: 4 }}>
              {u.title} — <span style={{ color: COLORS.usd }}>{u.reason}</span>
            </div>
          ))}
        </div>
      )}

      <div className="bl-table-wrap">
        <table className="bl-table">
          <thead>
            <tr>
              <th className="bl-th" style={{ textAlign: 'left' }}>task</th>
              <th className="bl-th" style={{ width: 140 }}>start</th>
              <th className="bl-th" style={{ width: 140 }}>end</th>
              <th className="bl-th" style={{ width: 80 }}>modified</th>
            </tr>
          </thead>
          <tbody>
            {eventList.map(([taskId, ev]) => (
              <tr key={taskId} className="bl-row">
                <td className="bl-td bl-title">{taskId.length > 50 ? taskId.slice(0, 47) + '…' : taskId}</td>
                <td className="bl-td" style={{ textAlign: 'center', color: COLORS.time }}>
                  {fmtSlot(ev.scheduled_start)}
                </td>
                <td className="bl-td" style={{ textAlign: 'center', color: COLORS.time }}>
                  {fmtSlot(ev.scheduled_end)}
                </td>
                <td className="bl-td" style={{ textAlign: 'center', color: ev.user_modified ? COLORS.usd : COLORS.dim }}>
                  {ev.user_modified ? 'yes' : '—'}
                </td>
              </tr>
            ))}
            {eventList.length === 0 && (
              <tr><td colSpan={4} className="bl-empty">no scheduled events</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
