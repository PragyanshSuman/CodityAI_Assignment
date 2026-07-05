import { useEffect, useRef, useState, useCallback } from 'react';

export function useWebSocket(onMessage) {
  const ws = useRef(null);
  const [connected, setConnected] = useState(false);
  const reconnectTimer = useRef(null);

  const connect = useCallback(() => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const url = `${protocol}//${window.location.host}/ws`;

    ws.current = new WebSocket(url);

    ws.current.onopen = () => {
      setConnected(true);
      // Keep-alive ping
      const ping = setInterval(() => {
        if (ws.current?.readyState === WebSocket.OPEN) {
          ws.current.send('ping');
        }
      }, 30000);
      ws.current._ping = ping;
    };

    ws.current.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        if (msg !== 'pong') onMessage?.(msg);
      } catch {}
    };

    ws.current.onclose = () => {
      setConnected(false);
      clearInterval(ws.current?._ping);
      // Reconnect after 3s
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    ws.current.onerror = () => {
      ws.current?.close();
    };
  }, [onMessage]);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      clearInterval(ws.current?._ping);
      ws.current?.close();
    };
  }, [connect]);

  return connected;
}
