export const COLORS = {
  neon:     '#87d787',
  neonDim:  '#005f00',
  pearl:    '#dadada',
  silver:   '#8a8a8a',
  dim:      '#6c6c6c',
  val:      '#dadada',
  delta:    '#00afff',
  mem:      '#87afaf',
  tool:     '#d7af87',
  time:     '#afafaf',
  tok:      '#87af87',
  usd:      '#ffaf87',
} as const;

export const HIGHLIGHT_TTL = 2000;
export const PRIORITY_RANK: Record<string, number> = { high: 0, medium: 1, low: 2 };

export function fmtDt(iso: string | null): string {
  if (!iso) return '—';
  try {
    const dt = new Date(iso);
    const day = String(dt.getDate()).padStart(2, '0');
    const mon = dt.toLocaleString('en-GB', { month: 'short' }).toUpperCase();
    const year = dt.getFullYear();
    const time = dt.toLocaleTimeString('en-GB', { hour12: false });
    return `${day}-${mon}-${year} ${time}`;
  } catch { return iso.slice(0, 19); }
}

export function fmtSize(kb: number | null): string {
  if (kb == null) return '—';
  if (kb >= 1024) return `${(kb / 1024).toFixed(1)} MB`;
  return `${kb.toFixed(1)} KB`;
}

export function fmtDuration(seconds: number | null): string {
  if (seconds == null || seconds < 0) return '—';
  const totalM = seconds / 60;
  if (totalM < 1) return `${Math.floor(seconds)}s`;
  const totalH = totalM / 60;
  if (totalH < 1) return `${Math.floor(totalM)}m`;
  const totalD = totalH / 24;
  if (totalD < 1) return `${totalH.toFixed(1)}h`;
  return `${totalD.toFixed(1)}d`;
}

export function fmtTokens(n: number | null): string {
  if (n == null) return '—';
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

export function fmtUsd(usd: number | null): string {
  if (usd == null) return '—';
  if (usd < 0.01) return `$${usd.toFixed(4)}`;
  return `$${usd.toFixed(3)}`;
}
