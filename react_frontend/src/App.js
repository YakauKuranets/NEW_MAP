import React, { useEffect } from 'react';
import Dashboard from './pages/Dashboard';
import useMapStore from './store/useMapStore';

function App() {
  const connectWebSocket = useMapStore((s) => s.connectWebSocket);

  useEffect(() => {
    if (connectWebSocket) {
      connectWebSocket();
    }
  }, [connectWebSocket]);

  return (
    <div className="App w-screen h-screen bg-slate-950 text-slate-100 overflow-hidden font-sans antialiased">
      <Dashboard />
    </div>
  );
}

export default App;