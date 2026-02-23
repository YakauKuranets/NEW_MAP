import { useEffect } from 'react';
import useMapStore from '../store/useMapStore';

export default function useWebSocket({
  url = process.env.REACT_APP_REALTIME_WS_URL || 'ws://localhost:8765',
  wsFactory,
} = {}) {
  const updateAgent = useMapStore((s) => s.updateAgent);
  const addIncident = useMapStore((s) => s.addIncident);

  useEffect(() => {
    const socket = wsFactory ? wsFactory(url) : new WebSocket(url);

    socket.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data || '{}');
        const eventName = message?.event;
        const data = message?.data;

        if (!eventName || !data) return;

        if (eventName === 'telemetry_update' || eventName === 'duty_location_update') {
          updateAgent(data);
          return;
        }

        if (
          eventName === 'pending_created'
          || eventName === 'incident_created'
          || eventName === 'NEW_INCIDENT'
        ) {
          addIncident(data);
        }
      } catch (_error) {
        // ignore malformed websocket frames
      }
    };

    return () => {
      if (socket && typeof socket.close === 'function') socket.close();
    };
  }, [url, wsFactory, updateAgent, addIncident]);
}
