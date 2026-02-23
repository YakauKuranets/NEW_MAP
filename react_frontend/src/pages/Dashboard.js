import React, { useState, useMemo } from 'react';
import DashboardLayout from '../components/DashboardLayout';
import CommandCenterMap from '../components/CommandCenterMap';
import IncidentFeed from '../components/IncidentFeed';
import VideoModal from '../components/VideoModal';
import ObjectInspector from '../components/ObjectInspector';
import IncidentChat from '../components/IncidentChat';
import IncidentChatPanel from '../components/IncidentChatPanel';
import PendingRequestsPanel from '../components/PendingRequestsPanel';
import useMapStore from '../store/useMapStore';

export default function Dashboard() {
  const [activeObjectId, setActiveObjectId] = useState(null);
  const [activeTab, setActiveTab] = useState('radar');
  const [theme, setTheme] = useState('dark');
  const [flyToTarget, setFlyToTarget] = useState(null);
  const [activeChatIncidentId, setActiveChatIncidentId] = useState(null);

  const trackers = useMapStore((s) => s.trackers);

  const selectedObjectData = useMemo(() => {
    if (!activeObjectId || !trackers[activeObjectId]) return null;
    return { id: activeObjectId, ...trackers[activeObjectId] };
  }, [activeObjectId, trackers]);

  const bgClass = theme === 'dark' ? 'bg-slate-950' : 'bg-slate-100';

  const renderContent = () => {
    switch (activeTab) {
      case 'radar':
        return (
          <>
            <div className="absolute inset-0">
              <CommandCenterMap
                theme={theme}
                flyToTarget={flyToTarget}
                onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
                onUserClick={(id) => setActiveObjectId(id)}
              />
            </div>
            <IncidentFeed theme={theme} />
            <IncidentChat />
            <div className="absolute inset-0 z-30 pointer-events-none">
              <PendingRequestsPanel onFlyToPending={setFlyToTarget} />
            </div>
          </>
        );
      case 'agents':
        return <div className={`p-10 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Раздел списка сотрудников (в разработке)</div>;
      case 'analytics':
        return <div className={`p-10 ${theme === 'dark' ? 'text-slate-400' : 'text-slate-500'}`}>Раздел аналитики и графиков (в разработке)</div>;
      default:
        return null;
    }
  };

  return (
    <DashboardLayout activeTab={activeTab} onTabChange={setActiveTab} theme={theme}>
      <div className={`relative h-full w-full transition-colors duration-500 ${bgClass}`}>
        {renderContent()}


        {activeChatIncidentId !== null && (
          <IncidentChatPanel
            incidentId={activeChatIncidentId}
            onClose={() => setActiveChatIncidentId(null)}
          />
        )}

        <ObjectInspector data={selectedObjectData} onClose={() => setActiveObjectId(null)} theme={theme} />
        <VideoModal userId={activeObjectId} onClose={() => setActiveObjectId(null)} theme={theme} />

        {activeTab === 'radar' && (
          <div className="pointer-events-none absolute left-1/2 top-1/2 z-10 -translate-x-1/2 -translate-y-1/2 transform opacity-20">
            <div className={`flex h-32 w-32 items-center justify-center rounded-full border transition-colors ${theme === 'dark' ? 'border-slate-500' : 'border-slate-400'}`}>
              <div className={`absolute top-0 h-4 w-1 ${theme === 'dark' ? 'bg-slate-500' : 'bg-slate-400'}`} />
              <div className={`absolute bottom-0 h-4 w-1 ${theme === 'dark' ? 'bg-slate-500' : 'bg-slate-400'}`} />
              <div className={`absolute left-0 h-1 w-4 ${theme === 'dark' ? 'bg-slate-500' : 'bg-slate-400'}`} />
              <div className={`absolute right-0 h-1 w-4 ${theme === 'dark' ? 'bg-slate-500' : 'bg-slate-400'}`} />
              <div className="h-1 w-1 rounded-full bg-red-500" />
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  );
}
