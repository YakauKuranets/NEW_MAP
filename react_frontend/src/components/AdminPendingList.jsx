import React from 'react';
import { Virtuoso } from 'react-virtuoso';
import { triggerImpact, triggerSelection } from '../utils/haptics';

const resolvePendingId = (pending) => String(pending?.id ?? pending?.pending ?? pending?.pending_id ?? '');

export default function AdminPendingList({
  pendingMarkers = [],
  onOpenPending,
  onApprovePending,
  onRejectPending,
}) {
  return (
    <section className="flex h-full min-h-0 flex-col rounded-2xl border border-yellow-500/40 bg-black/70 backdrop-blur-md">
      <header className="flex items-center gap-2 border-b border-yellow-500/30 px-3 py-2">
        <span className="text-xs font-black uppercase tracking-[0.15em] text-yellow-100">Pending moderation</span>
        <span className="ml-auto rounded border border-yellow-300/40 bg-yellow-300/10 px-2 py-0.5 text-[10px] font-bold text-yellow-200">
          {pendingMarkers.length}
        </span>
      </header>

      <div className="h-full min-h-0 pb-safe">
        <Virtuoso
          style={{ height: '100%' }}
          totalCount={pendingMarkers.length}
          itemContent={(index) => {
            const pending = pendingMarkers[index];
            const markerId = resolvePendingId(pending);

            return (
              <article className="border-b border-white/10 px-3 py-2.5">
                <button
                  type="button"
                  onClick={() => {
                    triggerSelection();
                    onOpenPending?.(pending);
                  }}
                  className="w-full text-left"
                >
                  <div className="text-[11px] uppercase tracking-wide text-yellow-200">
                    {pending?.author || pending?.reporter || pending?.user_id || 'Agent'}
                  </div>
                  <div className="mt-1 text-xs text-slate-100">
                    {pending?.type || pending?.category || 'Инцидент'}
                  </div>
                  <div className="mt-1 text-[11px] text-slate-300">
                    {pending?.description || pending?.title || pending?.address || 'Без описания'}
                  </div>
                </button>

                {pending?.photo_url || pending?.image ? (
                  <img
                    src={pending.photo_url || pending.image}
                    alt="pending marker"
                    className="mt-2 h-24 w-full rounded-lg object-cover"
                  />
                ) : null}

                <div className="mt-2 grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      triggerImpact('medium');
                      onApprovePending?.(pending, markerId);
                    }}
                    className="rounded-lg border border-cyan-400/50 bg-cyan-500/15 px-2 py-1.5 text-[11px] font-bold text-cyan-200 transition hover:bg-cyan-500/25"
                  >
                    ✓ Approve
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      triggerImpact('heavy');
                      onRejectPending?.(pending, markerId);
                    }}
                    className="rounded-lg border border-red-400/50 bg-red-500/15 px-2 py-1.5 text-[11px] font-bold text-red-200 transition hover:bg-red-500/25"
                  >
                    ✗ Reject
                  </button>
                </div>
              </article>
            );
          }}
        />
      </div>
    </section>
  );
}
