import type { Task } from '../sdk/types';
import { COLORS } from './constants';


function priorityLabel(p: string | null): string {
  if (p === 'high') return '⏫ high';
  if (p === 'medium') return '🔼 med';
  if (p === 'low') return '🔽 low';
  return '—';
}

function priorityColor(p: string | null): string {
  if (p === 'high') return COLORS.usd;
  if (p === 'medium') return COLORS.tok;
  if (p === 'low') return COLORS.time;
  return COLORS.dim;
}

function ageLabel(isoDate: string | null): string {
  if (!isoDate) return '—';
  const d = Math.floor((Date.now() - new Date(isoDate).getTime()) / 86400000);
  if (d === 0) return 'today';
  if (d < 30) return `${d}d`;
  return `${Math.floor(d / 30)}mo`;
}

function isOverdue(item: Task): boolean {
  if (item.state !== 'open') return false;
  const d = item.must_before || item.best_before;
  return d ? new Date(d) < new Date() : false;
}

interface Props {
  items: Task[];
  sortKey: string;
  sortDir: 'asc' | 'desc';
  onSort: (key: string) => void;
}

export function BacklogTable({ items, sortKey, sortDir, onSort }: Props) {
  function Th({ k, label, style }: { k: string; label: string; style?: React.CSSProperties }) {
    const active = sortKey === k;
    return (
      <th onClick={() => onSort(k)} className={`bl-th ${active ? 'bl-th-active' : ''}`} style={style}>
        {label}{active ? (sortDir === 'asc' ? ' ↑' : ' ↓') : ''}
      </th>
    );
  }

  return (
    <div className="bl-table-wrap">
      <table className="bl-table">
        <thead>
          <tr>
            <Th k="state" label="state" style={{ width: 52 }} />
            <Th k="title" label="title" style={{ textAlign: 'left' }} />
            <Th k="source" label="source" style={{ width: 130 }} />
            <Th k="priority" label="pri" style={{ width: 80 }} />
            <Th k="must_before" label="due" style={{ width: 96 }} />
            <Th k="best_before" label="sched" style={{ width: 96 }} />
            <Th k="age" label="age" style={{ width: 60 }} />
          </tr>
        </thead>
        <tbody>
          {items.map(item => {
            const od = isOverdue(item);
            return (
              <tr key={item.id} className={`bl-row${od ? ' bl-row-overdue' : ''}${item.state === 'closed' ? ' bl-row-closed' : ''}`}>
                <td className="bl-td" style={{ color: item.state === 'open' ? COLORS.neon : COLORS.dim, textAlign: 'center' }}>
                  {item.state === 'open' ? '○' : '✓'}
                </td>
                <td className="bl-td bl-title">
                  {item.url
                    ? <a href={item.url} target="_blank" rel="noreferrer" className="bl-link">{item.title}</a>
                    : item.title}
                  {item.file && <span className="bl-file"> {item.file}:{item.line}</span>}
                </td>
                <td className="bl-td bl-source" title={item.source_description} style={{ color: COLORS.dim }}>
                  {item.source_repo || 'obsidian'}
                </td>
                <td className="bl-td" style={{ color: priorityColor(item.priority), textAlign: 'center' }}>
                  {priorityLabel(item.priority)}
                </td>
                <td className="bl-td" style={{ color: od ? COLORS.usd : COLORS.time, textAlign: 'center' }}>
                  {item.must_before || '—'}
                </td>
                <td className="bl-td" style={{ color: COLORS.dim, textAlign: 'center' }}>
                  {item.best_before || '—'}
                </td>
                <td className="bl-td" style={{ color: COLORS.dim, textAlign: 'right' }}>
                  {ageLabel(item.created_at)}
                </td>
              </tr>
            );
          })}
          {items.length === 0 && (
            <tr><td colSpan={7} className="bl-empty">no items</td></tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
