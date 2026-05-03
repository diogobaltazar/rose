import { useEffect, useRef } from 'react';

export function useWebSocket<T>(
  path: string,
  onData: (data: T) => void,
): void {
  const wsRef = useRef<WebSocket | null>(null);
  const onDataRef = useRef(onData);
  onDataRef.current = onData;

  useEffect(() => {
    function connect() {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const ws = new WebSocket(`${proto}//${window.location.host}${path}`);
      wsRef.current = ws;

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data);
          if (Array.isArray(data)) {
            onDataRef.current(data as T);
          }
        } catch { /* ignore */ }
      };

      ws.onclose = () => {
        setTimeout(connect, 2000);
      };
    }

    connect();
    return () => wsRef.current?.close();
  }, [path]);
}
