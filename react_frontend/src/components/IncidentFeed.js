import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, MapPin, Clock, ExternalLink } from 'lucide-react';
import useMapStore from '../store/useMapStore';

export default function IncidentFeed({ theme = 'dark' }) {
  // ИСПРАВЛЕНИЕ: Используем markers вместо старых incidents
  const { markers = [], setActiveMarker } = useMapStore();

  const isDark = theme === 'dark';

  // Динамические стили в зависимости от темы
  const headerBg = isDark ? 'bg-slate-900/80 border-slate-700' : 'bg-white/90 border-slate-300 shadow-xl';
  const cardBg = isDark ? 'bg-slate-800/60 border-slate-700/50 hover:bg-slate-700/60' : 'bg-white/80 border-slate-200 shadow-md hover:bg-slate-50';
  const textPrimary = isDark ? 'text-slate-200' : 'text-slate-800';
  const textSecondary = isDark ? 'text-slate-400' : 'text-slate-500';

  return (
    <div className="absolute top-6 right-6 w-80 max-h-[85vh] overflow-y-auto z-40 pr-2 pointer-events-none custom-scrollbar">

      {/* Заголовок сводки */}
      <div className={`flex items-center gap-2 mb-4 pointer-events-auto backdrop-blur-md border p-3 rounded-xl shadow-2xl transition-colors duration-500 ${headerBg}`}>
        <AlertTriangle className={`w-5 h-5 animate-pulse ${isDark ? 'text-amber-500' : 'text-amber-600'}`} />
        <h2 className={`font-bold tracking-wider text-sm ${textPrimary}`}>
          ОПЕРАТИВНАЯ СВОДКА
        </h2>
        <span className="ml-auto bg-blue-500/20 text-blue-500 py-0.5 px-2 rounded-full text-[10px] font-black border border-blue-500/30">
          {markers.length}
        </span>
      </div>

      {/* Список объектов (Последние 10) */}
      <div className="flex flex-col gap-3 pointer-events-auto">
        <AnimatePresence>
          {[...markers].reverse().slice(0, 10).map((marker) => (
            <motion.div
              key={marker.id}
              initial={{ opacity: 0, x: 50, scale: 0.95 }}
              animate={{ opacity: 1, x: 0, scale: 1 }}
              exit={{ opacity: 0, scale: 0.9, x: 20 }}
              transition={{ duration: 0.4, type: "spring", stiffness: 100 }}
              onClick={() => setActiveMarker(marker.id)}
              className={`backdrop-blur-md border p-4 rounded-2xl transition-all cursor-pointer group ${cardBg}`}
            >
              <div className="flex justify-between items-start mb-2">
                <span className={`text-[9px] font-black uppercase tracking-widest px-2 py-1 rounded border ${
                  isDark ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' : 'bg-blue-50 text-blue-700 border-blue-200'
                }`}>
                  ОБЪЕКТ ФИКСИРОВАН
                </span>
                <span className={`text-[10px] flex items-center gap-1 font-mono ${textSecondary}`}>
                  <Clock className="w-3 h-3" />
                  {/* Используем ID как временную метку, если нет tsEpochMs */}
                  {new Date(parseInt(marker.id) || Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </span>
              </div>

              <h4 className={`text-sm font-bold mb-1 truncate ${textPrimary}`}>
                {marker.title || 'Безымянный объект'}
              </h4>

              <p className={`text-[11px] mb-3 line-clamp-2 leading-relaxed ${textSecondary}`}>
                {marker.description || 'Описание отсутствует в базе данных.'}
              </p>

              <div className={`flex justify-between items-center text-[10px] border-t pt-3 ${isDark ? 'border-white/5' : 'border-slate-200'}`}>
                <div className="flex items-center gap-1 opacity-70">
                  <MapPin className="w-3 h-3 text-rose-500" />
                  <span className="truncate w-32 font-mono">
                    {marker.lat?.toFixed(4)}, {marker.lon?.toFixed(4)}
                  </span>
                </div>
                {marker.url && (
                  <div className="flex items-center gap-1 text-blue-500 font-bold group-hover:underline">
                    <ExternalLink size={10} /> LINK
                  </div>
                )}
              </div>
            </motion.div>
          ))}
        </AnimatePresence>

        {markers.length === 0 && (
          <div className={`text-center py-10 opacity-30 italic text-xs ${textSecondary}`}>
            Ожидание входящих данных...
          </div>
        )}
      </div>

    </div>
  );
}