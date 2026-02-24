import localforage from 'localforage';

const MARKER_QUEUE_KEY = 'marker_sync_queue';
const MARKER_SYNC_ENDPOINT = process.env.REACT_APP_MARKER_SYNC_URL || '/api/markers';

const markerQueueStorage = localforage.createInstance({
  name: 'twa-marker-storage',
  storeName: 'markerQueue',
});

const normalizeQueue = (value) => (Array.isArray(value) ? value : []);

const notifySyncSuccess = () => {
  const tg = window?.Telegram?.WebApp;
  const haptic = tg?.HapticFeedback;
  if (!haptic || typeof haptic.notificationOccurred !== 'function') return;
  haptic.notificationOccurred('success');
};

export async function getMarkerQueue() {
  const queue = await markerQueueStorage.getItem(MARKER_QUEUE_KEY);
  return normalizeQueue(queue);
}

export async function saveMarkerToQueue(markerData) {
  const queue = await getMarkerQueue();
  const payload = {
    ...markerData,
    queuedAt: Date.now(),
  };

  const nextQueue = [...queue, payload];
  await markerQueueStorage.setItem(MARKER_QUEUE_KEY, nextQueue);
  return nextQueue;
}

export async function clearQueue() {
  await markerQueueStorage.removeItem(MARKER_QUEUE_KEY);
}

export async function syncMarkersQueue() {
  const queue = await getMarkerQueue();
  if (!queue.length) return { synced: 0 };

  for (const markerData of queue) {
    const response = await fetch(MARKER_SYNC_ENDPOINT, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(markerData),
    });

    if (!response.ok) {
      throw new Error('marker_sync_failed');
    }
  }

  await clearQueue();
  notifySyncSuccess();

  return { synced: queue.length };
}

export default {
  saveMarkerToQueue,
  getMarkerQueue,
  clearQueue,
  syncMarkersQueue,
};
