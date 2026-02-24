import { create } from '../vendor/zustand';

const SHIFT_STATUS_ENDPOINT = process.env.REACT_APP_SHIFT_STATUS_URL || '/api/shift/status';

const isNavigatorOnline = () => {
  if (typeof navigator === 'undefined') return true;
  return navigator.onLine;
};

const syncStatusWithServer = async (status) => {
  const response = await fetch(SHIFT_STATUS_ENDPOINT, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ status }),
  });

  if (!response.ok) {
    throw new Error('shift_status_sync_failed');
  }

  return response;
};

const useShiftStore = create((set, get) => ({
  status: 'offline',
  syncQueue: [],

  changeStatus: async (newStatus) => {
    set({ status: newStatus });

    try {
      await syncStatusWithServer(newStatus);
    } catch (_error) {
      set((state) => ({
        syncQueue: [
          ...state.syncQueue,
          {
            status: newStatus,
            queuedAt: Date.now(),
          },
        ],
      }));
    }
  },

  processQueue: async () => {
    if (!isNavigatorOnline()) return;

    const { syncQueue } = get();
    if (!syncQueue.length) return;

    const pending = [];

    for (const item of syncQueue) {
      try {
        await syncStatusWithServer(item.status);
      } catch (_error) {
        pending.push(item);
      }
    }

    set({ syncQueue: pending });
  },
}));

export default useShiftStore;
export { syncStatusWithServer };
