import React, { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { AlertTriangle, ChevronLeft, ChevronRight, MapPin, Clock3 } from 'lucide-react';
import useMapStore from '../store/useMapStore';

export default function IncidentFeed() {
  const incidents = useMapStore((s) => s.incidents);
  const [open, setOpen] = useState(true);

  const sorted = useMemo(
    () => [...(incidents || [])].sort((a, b) => Number(b.id || 0) - Number(a.id || 0)).slice(0, 20),
    [incidents],
  );

  return (
    <div className="pointer-events-none absolute right-0 top-20 z-40 h-[calc(100vh-6rem)]">
      <button
        className="pointer-events-auto absolute -left-10 top-4 rounded-l-xl border border-white/10 bg-black/60 px-2 py-2 text-cyber-blue backdrop-blur-md"
        onClick={() => setOpen((v) => !v)}
        aria-label="toggle incident feed"
      >
        {open ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.aside
            initial={{ x: 320, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            exit={{ x: 320, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="pointer-events-auto h-full w-80 border-l border-white/10 bg-black/35 backdrop-blur-cyber"
          >
            <div className="flex items-center gap-2 border-b border-white/10 p-4">
              <AlertTriangle className="h-4 w-4 text-alert-yellow" />
              <h3 className="text-sm font-black uppercase tracking-[0.16em] text-slate-100">Live Incidents</h3>
              <span className="ml-auto rounded-full border border-alert-yellow/30 bg-alert-yellow/10 px-2 py-0.5 text-[10px] font-black text-alert-yellow">
                {sorted.length}
              </span>
            </div>

            <div className="h-[calc(100%-58px)] space-y-2 overflow-y-auto p-3">
              {sorted.map((incident) => (
                <button
                  key={incident.id || `${incident.lat}-${incident.lon}`}
                  className="group w-full rounded-xl border border-white/10 bg-black/30 p-3 text-left transition hover:border-cyber-blue/70 hover:shadow-neon"
                >
                  <div className="mb-1 flex items-center justify-between">
                    <span className="text-[10px] font-black uppercase tracking-widest text-cyber-blue">
                      {incident.category || 'INCIDENT'}
                    </span>
                    <span className="inline-flex items-center gap-1 text-[10px] text-slate-400">
                      <Clock3 className="h-3 w-3" />
                      {new Date(Number(incident.id) || Date.now()).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                    </span>
                  </div>
                  <p className="line-clamp-2 text-xs text-slate-200">{incident.notes || incident.description || 'No description'}</p>
                  <div className="mt-2 inline-flex items-center gap-1 text-[11px] text-slate-400">
                    <MapPin className="h-3 w-3 text-alert-yellow" />
                    <span>
                      {Number(incident.lat || 0).toFixed(4)}, {Number(incident.lon || 0).toFixed(4)}
                    </span>
                  </div>
                </button>
              ))}

              {sorted.length === 0 && (
                <div className="rounded-xl border border-dashed border-white/10 p-4 text-center text-xs text-slate-400">
                  Waiting for realtime incidents...
                </div>
              )}
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
    </div>
  );
}
