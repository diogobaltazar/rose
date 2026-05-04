import { useState, useEffect, useRef, useCallback } from 'react';
import type { Task } from '../sdk/types';
import { client } from '../sdk/client';
import { GamificationPanel } from './GamificationPanel';
import { BacklogTable } from './BacklogTable';

const PRIORITY_RANK: Record<string, number> = { high: 0, medium: 1, low: 2 };

function BurnChart({ items }: { items: Task[] }) {
  const data = closedPerDay(items, 30);
  const max = Math.max(1, ...data.map(([, v]) => v));
  return (
    <div className="burn-chart">
      <div className="burn-chart-title">closed / day — 30d</div>
      <div className="burn-bars">
        {data.map(([day, count]) => (
          <div key={day} className="burn-bar-wrap" title={`${day}: ${count}`}>
            <div className="burn-bar" style={{ height: `${Math.max(2, Math.round((count / max) * 56))}px`, opacity: count === 0 ? 0.15 : 0.85 }} />
            {count > 0 && <div className="burn-bar-count">{count}</div>}
          </div>
        ))}
      </div>
    </div>
  );
}

function closedPerDay(items: Task[], days: number): [string, number][] {
  const counts: Record<string, number> = {};
  const now = new Date();
  for (let i = days - 1; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    counts[d.toISOString().slice(0, 10)] = 0;
  }
  for (const item of items) {
    if (item.state === 'closed' && item.closed_at) {
      const day = item.closed_at.slice(0, 10);
      if (day in counts) counts[day]++;
    }
  }
  return Object.entries(counts);
}

export function BacklogView() {
  const [allItems, setAllItems] = useState<Task[]>([]);
  const [filteredItems, setFilteredItems] = useState<Task[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [sortKey, setSortKey] = useState('state');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc');
  const [showClosed, setShowClosed] = useState(false);
  const [searching, setSearching] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);
  const searchTimeout = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => {
    function connect() {
      wsRef.current = client.connectBacklog((data) => {
        setAllItems(data);
        setLastSync(new Date().toLocaleTimeString());
      });
      wsRef.current.onclose = () => setTimeout(connect, 3000);
    }
    connect();
    return () => wsRef.current?.close();
  }, []);

  const doSearch = useCallback(async (query: string) => {
    if (!query.trim()) {
      setFilteredItems([]);
      setSearching(false);
      return;
    }
    setSearching(true);
    try {
      const results = await client.listTasks({
        search: query,
        sort: sortKey !== 'state' ? sortKey : undefined,
        order: sortDir,
        status: showClosed ? undefined : 'open',
      });
      setFilteredItems(results);
    } catch {
      setFilteredItems([]);
    }
    setSearching(false);
  }, [sortKey, sortDir, showClosed]);

  const handleSearchChange = (value: string) => {
    setSearchQuery(value);
    if (searchTimeout.current) clearTimeout(searchTimeout.current);
    searchTimeout.current = setTimeout(() => doSearch(value), 300);
  };

  function handleSort(key: string) {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc');
    else { setSortKey(key); setSortDir('asc'); }
  }

  async function handleRefresh() {
    setRefreshing(true);
    try { await client.refreshBacklog(); } catch { /* ignore */ }
    setRefreshing(false);
  }

  const isSearchActive = searchQuery.trim().length > 0;
  const sourceItems = isSearchActive ? filteredItems : allItems;
  const visible = showClosed ? sourceItems : sourceItems.filter(i => i.state === 'open');

  const sorted = [...visible].sort((a, b) => {
    let va: string | number, vb: string | number;
    if (sortKey === 'priority') { va = PRIORITY_RANK[a.priority || ''] ?? 9; vb = PRIORITY_RANK[b.priority || ''] ?? 9; }
    else if (sortKey === 'must_before') { va = a.must_before || 'zzzz'; vb = b.must_before || 'zzzz'; }
    else if (sortKey === 'best_before') { va = a.best_before || 'zzzz'; vb = b.best_before || 'zzzz'; }
    else if (sortKey === 'source') { va = a.source_repo || 'obsidian'; vb = b.source_repo || 'obsidian'; }
    else if (sortKey === 'age') { va = a.created_at || ''; vb = b.created_at || ''; }
    else { va = (a as unknown as Record<string, string>)[sortKey] || ''; vb = (b as unknown as Record<string, string>)[sortKey] || ''; }
    const c = String(va).localeCompare(String(vb));
    return sortDir === 'asc' ? c : -c;
  });

  return (
    <div className="backlog-view">
      <div className="backlog-toolbar">
        <span className="backlog-view-title">backlog</span>
        <input
          type="text"
          className="bl-search-input"
          placeholder="search…"
          value={searchQuery}
          onChange={e => handleSearchChange(e.target.value)}
        />
        {searching && <span className="bl-searching">…</span>}
        <label className="bl-toggle">
          <input type="checkbox" checked={showClosed} onChange={e => setShowClosed(e.target.checked)} />
          &nbsp;show closed
        </label>
        {lastSync && <span className="bl-sync-time">synced {lastSync}</span>}
        <button className={`bl-refresh-btn${refreshing ? ' refreshing' : ''}`} onClick={handleRefresh} disabled={refreshing}>
          {refreshing ? '↻ …' : '↻ refresh'}
        </button>
      </div>
      <GamificationPanel items={allItems} />
      <BurnChart items={allItems} />
      <BacklogTable items={sorted} sortKey={sortKey} sortDir={sortDir} onSort={handleSort} />
    </div>
  );
}
