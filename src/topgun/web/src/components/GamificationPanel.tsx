import type { Task } from '../sdk/types';
import { COLORS } from './constants';

function isOverdue(item: Task): boolean {
  if (item.state !== 'open') return false;
  const d = item.must_before || item.best_before;
  return d ? new Date(d) < new Date() : false;
}

function streakDays(items: Task[]): number {
  const closedDays = new Set(
    items.filter(i => i.state === 'closed' && i.closed_at).map(i => i.closed_at!.slice(0, 10))
  );
  let streak = 0;
  const now = new Date();
  for (let i = 0; i < 365; i++) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    if (closedDays.has(d.toISOString().slice(0, 10))) streak++;
    else if (i > 0) break;
  }
  return streak;
}

function weeklyVelocity(items: Task[]): { thisWeek: number; lastWeek: number } {
  const now = Date.now();
  const W = 7 * 86400000;
  let thisWeek = 0, lastWeek = 0;
  for (const item of items) {
    if (item.state !== 'closed' || !item.closed_at) continue;
    const age = now - new Date(item.closed_at).getTime();
    if (age < W) thisWeek++;
    else if (age < 2 * W) lastWeek++;
  }
  return { thisWeek, lastWeek };
}

interface Props {
  items: Task[];
}

export function GamificationPanel({ items }: Props) {
  const streak = streakDays(items);
  const { thisWeek, lastWeek } = weeklyVelocity(items);
  const delta = thisWeek - lastWeek;
  const overdue = items.filter(isOverdue).length;
  const open = items.filter(i => i.state === 'open').length;
  const closed = items.filter(i => i.state === 'closed').length;

  return (
    <div className="gamification-panel">
      <div className="gp-stat">
        <span className="gp-value" style={{ color: streak > 0 ? COLORS.usd : COLORS.dim }}>{streak}🔥</span>
        <span className="gp-label">streak</span>
      </div>
      <div className="gp-stat">
        <span className="gp-value" style={{ color: delta >= 0 ? COLORS.neon : COLORS.usd }}>
          {thisWeek}{delta > 0 ? '↑' : delta < 0 ? '↓' : ''}
        </span>
        <span className="gp-label">this week (vs {lastWeek})</span>
      </div>
      <div className="gp-stat">
        <span className="gp-value" style={{ color: overdue > 0 ? COLORS.usd : COLORS.dim }}>{overdue}</span>
        <span className="gp-label">overdue</span>
      </div>
      <div className="gp-stat">
        <span className="gp-value" style={{ color: COLORS.tok }}>{open}</span>
        <span className="gp-label">open</span>
      </div>
      <div className="gp-stat">
        <span className="gp-value" style={{ color: COLORS.silver }}>{closed}</span>
        <span className="gp-label">done</span>
      </div>
    </div>
  );
}
