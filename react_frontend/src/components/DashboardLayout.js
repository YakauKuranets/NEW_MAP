import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ShieldAlert, Map, Users, Settings, Activity,
  MapPin, Trash2, Crosshair, ExternalLink, Plus, Edit3, Monitor, Cctv
} from 'lucide-react';
import useMapStore from '../store/useMapStore';

export default function DashboardLayout({ children, activeTab, onTabChange, theme = 'dark' }) {
  const isDark = theme === 'dark';

  const {
    markers = [],
    deleteMarker,
    setActiveMarker,
    activeMarkerId,
    setDraftMarker
  } = useMapStore();

  const asideBg = isDark
    ? 'bg-slate-900/90 border-slate-800'
    : 'bg-white border-slate-200 shadow-2xl';

  const logoText = isDark ? 'from-blue-400 to-cyan-300' : 'from-blue-600 to-cyan-500';

  const handleManualAdd = () => {
    setDraftMarker({
      lon: 27.56,
      lat: 53.9,
      address: '',
      title: '',
      description: '',
      url: '',
      image: '',
      cameraType: 'remote'
    });
  };

  return (
    <div className={`flex h-screen w-full overflow-hidden font-sans transition-colors duration-500 ${isDark ? 'bg-slate-950 text-slate-100' : 'bg-slate-50 text-slate-900'}`}>

      {/* ЛЕВАЯ ПАНЕЛЬ С УПРАВЛЕНИЕМ ОБЪЕКТАМИ */}
      <motion.aside
        initial={{ x: -100, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        className={`w-20 lg:w-80 backdrop-blur-md border-r flex flex-col z-50 transition-colors duration-500 ${asideBg}`}
      >
        {/* LOGO */}
        <div className="flex items-center gap-3 px-6 py-8 w-full">
          <ShieldAlert className="w-8 h-8 text-blue-500" />
          <h1 className={`text-xl font-black hidden lg:block tracking-tighter bg-clip-text text-transparent bg-gradient-to-r ${logoText}`}>
            PLAYE PRO v4
          </h1>
        </div>

        {/* MAIN NAV */}
        <nav className="flex flex-col gap-2 w-full px-4 mb-8">
          <NavItem theme={theme} active={activeTab === 'radar'} onClick={() => onTabChange('radar')} icon={<Map />} label="Радар объектов" />
          <NavItem theme={theme} active={activeTab === 'agents'} onClick={() => onTabChange('agents')} icon={<Users />} label="Сотрудники" />
        </nav>

        {/* СПИСОК АДРЕСОВ / МЕТОК */}
        <div className="flex-1 flex flex-col overflow-hidden border-t border-slate-800/50">
          <div className="px-6 py-4 flex justify-between items-center">
            <span className={`text-[10px] font-bold uppercase tracking-widest ${isDark ? 'text-slate-500' : 'text-slate-400'}`}>
              Список объектов ({markers?.length || 0})
            </span>

            {/* КНОПКА ДОБАВЛЕНИЯ */}
            <button
              onClick={handleManualAdd}
              className={`p-1.5 rounded-lg border transition-all hover:scale-110 active:scale-95 ${
                isDark
                  ? 'bg-blue-600/20 border-blue-500/30 text-blue-400 hover:bg-blue-600/40'
                  : 'bg-blue-50 border-blue-200 text-blue-600 hover:bg-blue-100'
              }`}
              title="Добавить объект"
            >
              <Plus size={16} />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto px-4 space-y-3 custom-scrollbar">
            <AnimatePresence>
              {markers && markers.map((marker) => (
                <MarkerListItem
                  key={marker.id}
                  marker={marker}
                  theme={theme}
                  isActive={activeMarkerId === marker.id}
                  onSelect={() => setActiveMarker(marker.id)}
                  onDelete={() => deleteMarker(marker.id)}
                />
              ))}
            </AnimatePresence>

            {(!markers || markers.length === 0) && (
              <div className="text-center py-10 opacity-30">
                <MapPin className="w-8 h-8 mx-auto mb-2" />
                <p className="text-xs font-medium">Объектов пока нет.<br/>Кликните ПКМ по карте<br/>или используйте "+".</p>
              </div>
            )}
          </div>
        </div>

        {/* BOTTOM NAV */}
        <div className="p-4 border-t border-slate-800/50">
          <NavItem theme={theme} active={activeTab === 'settings'} onClick={() => onTabChange('settings')} icon={<Settings />} label="Настройки" />
        </div>
      </motion.aside>

      {/* КАРТА / КОНТЕНТ */}
      <main className="flex-1 relative bg-slate-900">
        {children}
      </main>
    </div>
  );
}

function MarkerListItem({ marker, theme, isActive, onSelect, onDelete }) {
  const isDark = theme === 'dark';
  const { setDraftMarker } = useMapStore();

  // Определяем иконку по типу камеры (локальная/удаленная)
  const isLocal = marker.cameraType === 'local';
  const Icon = isLocal ? Monitor : Cctv;
  const iconColor = isLocal ? 'text-blue-400' : 'text-rose-400';
  const iconBg = isLocal ? 'bg-blue-500/10' : 'bg-rose-500/10';

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      onClick={onSelect}
      className={`group relative p-3 rounded-2xl border cursor-pointer transition-all duration-300 ${
        isActive
          ? (isDark ? 'bg-blue-600/20 border-blue-500/50' : 'bg-blue-50 border-blue-200 shadow-md')
          : (isDark ? 'bg-slate-800/30 border-slate-700/50 hover:border-slate-500' : 'bg-white border-slate-200 hover:shadow-lg')
      }`}
    >
      <div className="flex gap-3 items-start">
        {/* ИСПРАВЛЕНИЕ: Аккуратная иконка вместо фото */}
        <div className={`w-8 h-8 rounded-lg flex-shrink-0 flex items-center justify-center ${iconBg} ${iconColor} border ${isDark ? 'border-white/5' : 'border-black/5'}`}>
          <Icon size={14} />
        </div>

        <div className="flex-1 min-w-0">
          <h4 className={`text-xs font-bold truncate ${isDark ? 'text-slate-100' : 'text-slate-800'}`}>
            {marker.title || "БЕЗ НАЗВАНИЯ"}
          </h4>
          <p className="text-[10px] text-slate-500 truncate mt-0.5">
            {marker.address || "Адрес не указан"}
          </p>

          {/* ИНЖЕНЕРНЫЙ БЛОК КНОПОК УПРАВЛЕНИЯ */}
          <div className={`flex gap-1.5 mt-3 items-center justify-end transition-opacity ${isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}>

            {marker.url && (
              <a
                href={marker.url}
                target="_blank"
                rel="noreferrer"
                onClick={(e) => e.stopPropagation()}
                className="p-1.5 bg-slate-500/10 text-slate-400 rounded-lg hover:bg-slate-500/20 transition-colors mr-auto"
                title="Перейти по ссылке"
              >
                <ExternalLink size={14} />
              </a>
            )}

            <button
              onClick={(e) => { e.stopPropagation(); onSelect(); }}
              className="p-1.5 bg-blue-500/10 text-blue-400 rounded-lg hover:bg-blue-500/20 transition-colors"
              title="Навести на карте"
            >
              <Crosshair size={14} />
            </button>

            <button
              onClick={(e) => { e.stopPropagation(); setDraftMarker(marker); }}
              className="p-1.5 bg-amber-500/10 text-amber-500 rounded-lg hover:bg-amber-500/20 transition-colors"
              title="Редактировать объект"
            >
              <Edit3 size={14} />
            </button>

            <button
              onClick={(e) => { e.stopPropagation(); onDelete(); }}
              className="p-1.5 bg-rose-500/10 text-rose-500 rounded-lg hover:bg-rose-500/20 transition-colors"
              title="Удалить объект"
            >
              <Trash2 size={14} />
            </button>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function NavItem({ icon, label, active, onClick, theme }) {
  const isDark = theme === 'dark';
  const activeStyles = isDark
    ? 'bg-blue-600/20 text-blue-400 shadow-[0_0_15px_rgba(37,99,235,0.2)]'
    : 'bg-blue-100 text-blue-700 border border-blue-200';
  const inactiveStyles = isDark
    ? 'text-slate-400 hover:bg-slate-800 hover:text-slate-100'
    : 'text-slate-500 hover:bg-slate-100 hover:text-slate-900';

  return (
    <button onClick={onClick} className={`flex items-center gap-3 p-3 rounded-xl transition-all duration-300 w-full ${active ? activeStyles : inactiveStyles}`}>
      <div className="w-5 h-5">{icon}</div>
      <span className="hidden lg:block font-bold text-xs uppercase tracking-wider">{label}</span>
    </button>
  );
}
