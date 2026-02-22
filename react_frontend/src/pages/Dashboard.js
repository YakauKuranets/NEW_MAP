import React, { useState, useMemo } from 'react';
import DashboardLayout from '../components/DashboardLayout';
import CommandCenterMap from '../components/CommandCenterMap';
import IncidentFeed from '../components/IncidentFeed';
import VideoModal from '../components/VideoModal';
import ObjectInspector from '../components/ObjectInspector';
import useMapStore from '../store/useMapStore';

export default function Dashboard() {
  const [activeObjectId, setActiveObjectId] = useState(null);
  const [activeTab, setActiveTab] = useState('radar');

  // === ВОТ ОНО! ГЛОБАЛЬНОЕ СОСТОЯНИЕ ТЕМЫ ===
  // По умолчанию ставим 'dark' (Киберпанк), чтобы стартовало черным
  const [theme, setTheme] = useState('dark');

  const trackers = useMapStore((s) => s.trackers);

  const selectedObjectData = useMemo(() => {
    if (!activeObjectId || !trackers[activeObjectId]) return null;
    return { id: activeObjectId, ...trackers[activeObjectId] };
  }, [activeObjectId, trackers]);

  // Меняем фон самого экрана под картой
  const bgClass = theme === 'dark' ? 'bg-slate-950' : 'bg-slate-100';

  const renderContent = () => {
    switch (activeTab) {
      case 'radar':
        return (
          <>
            <div className="absolute inset-0">
              <CommandCenterMap
                theme={theme} // Передаем текущую тему в карту
                onToggleTheme={() => setTheme(theme === 'dark' ? 'light' : 'dark')} // Кнопка переключает тему!
                onUserClick={(id) => setActiveObjectId(id)}
              />
            </div>
            <IncidentFeed theme={theme} />
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
    // Передаем тему в левое меню, чтобы оно тоже меняло цвет
    <DashboardLayout activeTab={activeTab} onTabChange={setActiveTab} theme={theme}>
      <div className={`relative w-full h-full transition-colors duration-500 ${bgClass}`}>

        {renderContent()}

        {/* ПЕРЕДАЕМ ТЕМУ В КАРТОЧКУ И ВИДЕО */}
        <ObjectInspector data={selectedObjectData} onClose={() => setActiveObjectId(null)} theme={theme} />
        <VideoModal userId={activeObjectId} onClose={() => setActiveObjectId(null)} theme={theme} />

        {/* Декоративный прицел (HUD) */}
        {activeTab === 'radar' && (
          <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 pointer-events-none opacity-20 z-10">
            <div className={`w-32 h-32 border rounded-full flex items-center justify-center transition-colors ${theme === 'dark' ? 'border-slate-500' : 'border-slate-400'}`}>
              <div className={`w-1 h-4 absolute top-0 ${theme === 'dark' ? 'bg-slate-500' : 'bg-slate-400'}`}></div>
              <div className={`w-1 h-4 absolute bottom-0 ${theme === 'dark' ? 'bg-slate-500' : 'bg-slate-400'}`}></div>
              <div className={`w-4 h-1 absolute left-0 ${theme === 'dark' ? 'bg-slate-500' : 'bg-slate-400'}`}></div>
              <div className={`w-4 h-1 absolute right-0 ${theme === 'dark' ? 'bg-slate-500' : 'bg-slate-400'}`}></div>
              <div className="w-1 h-1 bg-red-500 rounded-full"></div>
            </div>
          </div>
        )}

      </div>
    </DashboardLayout>
  );
}