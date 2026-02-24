import React, { useEffect } from 'react';
import Dashboard from './pages/Dashboard';
import useWebSocket from './hooks/useWebSocket';
import { setupTelegramWebApp } from './utils/twaSetup';
import ShiftControlBar from './components/ShiftControlBar';
import useShiftStore from './store/useShiftStore';
import { syncMarkersQueue } from './store/markerQueue';

function App() {
  useWebSocket();

  useEffect(() => {
    setupTelegramWebApp();
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return undefined;

    const processQueueOnReconnect = () => {
      useShiftStore.getState().processQueue();
      syncMarkersQueue().catch(() => {
        // keep offline queue for next retry cycle
      });
    };

    window.addEventListener('online', processQueueOnReconnect);
    return () => window.removeEventListener('online', processQueueOnReconnect);
  }, []);

  return (
    <div className="App w-screen h-screen bg-slate-950 text-slate-100 overflow-hidden font-sans antialiased">
      <Dashboard />
      <ShiftControlBar />
    </div>
  );
}

export default App;
