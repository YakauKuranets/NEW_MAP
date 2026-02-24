import React, { useState, useMemo } from 'react';
import { ViewMode } from '@nebula.gl/edit-modes';
import DashboardLayout from '../components/DashboardLayout';
import CommandCenterMap from '../components/CommandCenterMap';
import IncidentFeed from '../components/IncidentFeed';
import VideoModal from '../components/VideoModal';
import ObjectInspector from '../components/ObjectInspector';
import IncidentChat from '../components/IncidentChat';
import IncidentChatPanel from '../components/IncidentChatPanel';
import PendingRequestsPanel from '../components/PendingRequestsPanel';
import TimelineSlider from '../components/TimelineSlider';
import GeofenceToolbar from '../components/GeofenceToolbar';
import { timelineMinTime, timelineMaxTime } from '../mocks/tripsData';
import useTimelineAnimation from '../hooks/useTimelineAnimation';
import useGeofenceMonitor from '../hooks/useGeofenceMonitor';
import useMapStore from '../store/useMapStore';

const createEmptyGeofences = () => ({ type: 'FeatureCollection', features: [] });

export default function Dashboard() {
  const [activeObjectId, setActiveObjectId] = useState(null);
  const [activeTab, setActiveTab] = useState('radar');
  const [theme, setTheme] = useState('dark');
  const [flyToTarget, setFlyToTarget] = useState(null);
  const [activeChatIncidentId, setActiveChatIncidentId] = useState(null);
  const [geofenceFeatures, setGeofenceFeatures] = useState(() => createEmptyGeofences());
  const [geofenceMode, setGeofenceMode] = useState(() => ViewMode);

  const {
    currentTime: timelineTime,
    isPlaying: isTimelinePlaying,
    speedMultiplier: timelineSpeedMultiplier,
    seekTime: seekTimelineTime,
    setSpeed: setTimelineSpeed,
    togglePlay: toggleTimelinePlay,
  } = useTimelineAnimation({
    minTime: timelineMinTime,
    maxTime: timelineMaxTime,
    initialTime: timelineMinTime,
    loop: false,
  });

  const trackers = useMapStore((s) => s.trackers);
  const agentsMap = useMapStore((s) => s.agents);

  const activeAgents = useMemo(() => Object.values(agentsMap || {}), [agentsMap]);
  const { violatingAgentIds, alerts } = useGeofenceMonitor(activeAgents, geofenceFeatures);

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
                timelineCurrentTime={timelineTime}
                geofenceFeatures={geofenceFeatures}
                geofenceMode={geofenceMode}
                onGeofenceEdit={setGeofenceFeatures}
                violatingAgentIds={violatingAgentIds}
              />
            </div>

            <GeofenceToolbar
              mode={geofenceMode}
              onModeChange={setGeofenceMode}
              onClear={() => setGeofenceFeatures(createEmptyGeofences())}
            />

            <IncidentFeed theme={theme} />
            <IncidentChat />
            <PendingRequestsPanel onFlyToPending={setFlyToTarget} />
            <TimelineSlider
              currentTime={timelineTime}
              minTime={timelineMinTime}
              maxTime={timelineMaxTime}
              isPlaying={isTimelinePlaying}
              speedMultiplier={timelineSpeedMultiplier}
              onTogglePlay={toggleTimelinePlay}
              onSeek={seekTimelineTime}
              onSpeedChange={setTimelineSpeed}
            />

            <div className="absolute right-4 top-4 z-50 flex max-w-md flex-col gap-2">
              {alerts.map((alert) => (
                <div key={alert.id} className="rounded-md border border-red-500/60 bg-red-950/90 px-3 py-2 text-xs text-red-100 shadow-lg">
                  {alert.message}
                </div>
              ))}
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
