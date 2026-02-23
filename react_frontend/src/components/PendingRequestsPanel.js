import React, { useEffect, useMemo, useState } from 'react';
import useMapStore from '../store/useMapStore';

const LIST_ENDPOINT = process.env.REACT_APP_PENDING_LIST_URL || '/api/pending';
const APPROVE_ENDPOINT = process.env.REACT_APP_PENDING_APPROVE_URL || '/api/pending';
const REJECT_ENDPOINT = process.env.REACT_APP_PENDING_REJECT_URL || '/api/pending';

const toNumber = (value) => {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
};

export default function PendingRequestsPanel({ onFlyToPending }) {
  const pendingMarkers = useMapStore((s) => s.pendingMarkers);
  const setPendingMarkers = useMapStore((s) => s.setPendingMarkers);
  const removePendingMarker = useMapStore((s) => s.removePendingMarker);
  const setActivePendingMarker = useMapStore((s) => s.setActivePendingMarker);
  const activePendingMarkerId = useMapStore((s) => s.activePendingMarkerId);
  const addIncident = useMapStore((s) => s.addIncident);

  const [isOpen, setIsOpen] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    let mounted = true;

    const loadPending = async () => {
      try {
        const response = await fetch(LIST_ENDPOINT);
        if (!response.ok) return;
        const payload = await response.json();
        if (mounted) setPendingMarkers(Array.isArray(payload) ? payload : []);
      } catch (_e) {
        // best effort only
      }
    };

    loadPending();

    return () => {
      mounted = false;
    };
  }, [setPendingMarkers]);

  const selectedPending = useMemo(() => {
    if (!activePendingMarkerId) return null;
    return pendingMarkers.find((item) => String(item.id ?? item.pending ?? item.pending_id) === String(activePendingMarkerId)) || null;
  }, [pendingMarkers, activePendingMarkerId]);

  const focusPending = (pending) => {
    const markerId = String(pending.id ?? pending.pending ?? pending.pending_id);
    setActivePendingMarker(markerId);
    const lon = toNumber(pending.lon ?? pending.longitude);
    const lat = toNumber(pending.lat ?? pending.latitude);
    if (lon !== null && lat !== null && onFlyToPending) {
      onFlyToPending({ lon, lat, id: markerId });
    }
  };

  const approvePending = async (pending) => {
    if (!pending || isSubmitting) return;
    const markerId = String(pending.id ?? pending.pending ?? pending.pending_id);

    setIsSubmitting(true);
    try {
      const response = await fetch(`${APPROVE_ENDPOINT}/${markerId}/approve`, { method: 'POST' });
      if (!response.ok) throw new Error('approve_failed');

      removePendingMarker(markerId);

      const lon = toNumber(pending.lon ?? pending.longitude);
      const lat = toNumber(pending.lat ?? pending.latitude);
      if (lon !== null && lat !== null) {
        addIncident({
          ...pending,
          id: pending.address_id || pending.id,
          lon,
          lat,
          status: 'approved',
          source: 'pending',
        });
      }
    } catch (_e) {
      // no-op in UI, websocket may still deliver eventual state
    } finally {
      setIsSubmitting(false);
    }
  };

  const rejectPending = async (pending) => {
    if (!pending || isSubmitting) return;
    const markerId = String(pending.id ?? pending.pending ?? pending.pending_id);

    setIsSubmitting(true);
    try {
      const response = await fetch(`${REJECT_ENDPOINT}/${markerId}/reject`, { method: 'POST' });
      if (!response.ok) throw new Error('reject_failed');
      removePendingMarker(markerId);
    } catch (_e) {
      // no-op in UI, websocket may still deliver eventual state
    } finally {
      setIsSubmitting(false);
    }
  };

  useEffect(() => {
    const onKeyDown = (event) => {
      if (!selectedPending || isSubmitting) return;
      if (event.key === 'Enter') {
        event.preventDefault();
        approvePending(selectedPending);
      }
      if (event.key === 'Delete') {
        event.preventDefault();
        rejectPending(selectedPending);
      }
    };

    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [selectedPending, isSubmitting]);

  return (
    <aside className="pointer-events-auto absolute right-0 top-14 z-40 h-[calc(100%-56px)] w-96 border-l border-yellow-300/30 bg-black/45 backdrop-blur-md">
      <div className="flex items-center gap-2 border-b border-yellow-300/20 px-4 py-3">
        <button
          type="button"
          onClick={() => setIsOpen((prev) => !prev)}
          className="rounded border border-yellow-300/40 bg-yellow-300/10 px-2 py-1 text-xs text-yellow-200"
        >
          {isOpen ? 'Свернуть' : 'Развернуть'}
        </button>
        <div className="text-sm font-semibold uppercase tracking-wider text-yellow-100">Входящие сигналы</div>
        <div className="ml-auto rounded-full border border-yellow-300/40 px-2 py-0.5 text-xs text-yellow-200">{pendingMarkers.length}</div>
      </div>

      {isOpen ? (
        <div className="h-[calc(100%-57px)] overflow-y-auto p-3">
          <div className="space-y-2">
            {pendingMarkers.map((pending) => {
              const markerId = String(pending.id ?? pending.pending ?? pending.pending_id);
              const isActive = markerId === String(activePendingMarkerId);
              return (
                <div
                  key={markerId}
                  className={`rounded-lg border p-3 ${isActive ? 'border-yellow-200 bg-yellow-300/10' : 'border-white/10 bg-black/30'}`}
                >
                  <button type="button" onClick={() => focusPending(pending)} className="w-full text-left">
                    <div className="text-xs uppercase tracking-wider text-yellow-200">{pending.category || 'signal'}</div>
                    <div className="mt-1 text-sm text-slate-100">{pending.name || pending.title || pending.address || 'Новая заявка'}</div>
                    <div className="mt-1 text-xs text-slate-400">{pending.notes || pending.description || 'Без описания'}</div>
                  </button>

                  {isActive ? (
                    <div className="mt-3 grid grid-cols-2 gap-2">
                      <button
                        type="button"
                        onClick={() => approvePending(pending)}
                        disabled={isSubmitting}
                        className="rounded border border-emerald-400/50 bg-emerald-500/20 px-2 py-1.5 text-xs text-emerald-200"
                      >
                        ✓ Подтвердить (Enter)
                      </button>
                      <button
                        type="button"
                        onClick={() => rejectPending(pending)}
                        disabled={isSubmitting}
                        className="rounded border border-red-400/50 bg-red-500/20 px-2 py-1.5 text-xs text-red-200"
                      >
                        ✗ Отклонить (Del)
                      </button>
                    </div>
                  ) : null}
                </div>
              );
            })}
          </div>

          {pendingMarkers.length === 0 ? (
            <div className="mt-4 rounded-lg border border-dashed border-white/20 p-4 text-center text-xs text-slate-400">
              Новых заявок нет.
            </div>
          ) : null}
        </div>
      ) : null}
    </aside>
  );
}
