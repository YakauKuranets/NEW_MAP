import React from 'react';
import { Cpu, Activity, ShieldCheck } from 'lucide-react';
import useMapStore from '../store/useMapStore';

function StatusPill({ label, online = true }) {
  return (
    <div className="flex items-center gap-2 rounded-full border border-white/10 bg-black/30 px-3 py-1.5 text-[10px] uppercase tracking-wider text-slate-200">
      <span className={`h-2 w-2 rounded-full ${online ? 'bg-emerald-400' : 'bg-neon-red'}`} />
      <span className="opacity-80">{label}</span>
    </div>
  );
}

export default function TopBar() {
  const agents = useMapStore((s) => s.agents);
  const activeAgents = Object.keys(agents || {}).length;

  return (
    <div className="pointer-events-auto absolute left-0 right-0 top-0 z-50 border-b border-white/10 bg-black/40 backdrop-blur-md">
      <div className="flex h-14 items-center justify-between px-4 md:px-6">
        <div className="flex items-center gap-3 text-cyber-blue">
          <ShieldCheck className="h-5 w-5" />
          <span className="text-sm font-black uppercase tracking-[0.2em]">Command Center v4.0</span>
        </div>

        <div className="hidden items-center gap-2 md:flex">
          <StatusPill label="Rust Gateway" online />
          <StatusPill label="Redis Bridge" online />
          <StatusPill label="WebSocket" online />
        </div>

        <div className="flex items-center gap-2 rounded-xl border border-cyber-blue/30 bg-cyber-blue/10 px-3 py-1.5 text-cyber-blue shadow-neon">
          <Activity className="h-4 w-4" />
          <span className="text-xs font-bold uppercase tracking-wider">Agents: {activeAgents}</span>
          <Cpu className="h-4 w-4 opacity-80" />
        </div>
      </div>
    </div>
  );
}
