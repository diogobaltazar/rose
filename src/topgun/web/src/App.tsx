import { useState, useMemo } from 'react';
import type { Session } from './sdk/types';
import { useWebSocket } from './hooks/useWebSocket';
import { Sidebar } from './components/Sidebar';
import { SessionDetail } from './components/SessionDetail';
import { BacklogView } from './components/BacklogView';
import { CalendarView } from './components/CalendarView';

export function App() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [activeView, setActiveView] = useState('observe');

  useWebSocket<Session[]>('/ws', (data) => {
    setSessions(data);
    setSelectedId(prev => {
      if (prev) return prev;
      const live = data.filter(s => s.status === 'live');
      live.sort((a, b) => (b.started_at || '').localeCompare(a.started_at || ''));
      return live[0]?.session_id || data[0]?.session_id || null;
    });
  });

  const selectedSession = useMemo(
    () => sessions.find(s => s.session_id === selectedId) || null,
    [sessions, selectedId]
  );

  function renderMain() {
    switch (activeView) {
      case 'backlog': return <BacklogView />;
      case 'calendar': return <CalendarView />;
      default: return <SessionDetail session={selectedSession} />;
    }
  }

  return (
    <div id="layout">
      <Sidebar
        sessions={sessions}
        selectedId={selectedId}
        onSelect={setSelectedId}
        activeView={activeView}
        onViewChange={setActiveView}
      />
      <div id="main">
        {renderMain()}
      </div>
    </div>
  );
}
