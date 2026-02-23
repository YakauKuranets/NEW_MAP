import { create } from '../vendor/zustand';

const initialState = {
  agents: {},
  incidents: [],
  selectedObject: null,
  trackers: {},
  statuses: {},
  markers: [],
  activeMarkerId: null,
  draftMarker: null,
};

const useMapStore = create((set) => ({
  ...initialState,

  updateAgent: (data) => set((state) => {
    const rawId = data?.agent_id ?? data?.id ?? data?.user_id;
    if (rawId === undefined || rawId === null) return state;

    const agentId = String(rawId);
    const mergedAgent = {
      ...(state.agents[agentId] || {}),
      ...data,
      agent_id: agentId,
    };

    return {
      agents: {
        ...state.agents,
        [agentId]: mergedAgent,
      },
      trackers: {
        ...state.trackers,
        [agentId]: {
          ...(state.trackers[agentId] || {}),
          ...mergedAgent,
        },
      },
      statuses: {
        ...state.statuses,
        [agentId]: data?.status || state.statuses[agentId] || 'online',
      },
    };
  }),

  addIncident: (data) => set((state) => {
    if (!data) return state;

    const incidentId = data.id ?? data.incident_id;
    if (incidentId === undefined || incidentId === null) {
      return { incidents: [data, ...state.incidents] };
    }

    const normalizedId = String(incidentId);
    const existingIdx = state.incidents.findIndex((it) => String(it.id ?? it.incident_id) === normalizedId);
    if (existingIdx >= 0) {
      const next = [...state.incidents];
      next[existingIdx] = { ...next[existingIdx], ...data, id: incidentId };
      return { incidents: next };
    }

    return { incidents: [{ ...data, id: incidentId }, ...state.incidents] };
  }),

  removeIncident: (incidentId) => set((state) => ({
    incidents: state.incidents.filter((it) => String(it.id ?? it.incident_id) !== String(incidentId)),
  })),

  setSelectedObject: (selectedObject) => set({ selectedObject }),

  // compatibility with older components
  upsertTrackerPosition: (trackerId, payload) => set((state) => ({
    trackers: {
      ...state.trackers,
      [String(trackerId)]: {
        ...(state.trackers[String(trackerId)] || {}),
        ...payload,
      },
    },
  })),

  setTrackerStatus: (trackerId, status) => set((state) => ({
    statuses: {
      ...state.statuses,
      [String(trackerId)]: status,
    },
  })),

  setDraftMarker: (data) => set({ draftMarker: data, activeMarkerId: null }),
  clearDraftMarker: () => set({ draftMarker: null }),

  addMarker: (markerData) => set((state) => ({
    markers: [...state.markers, { id: markerData?.id || Date.now().toString(), ...markerData }],
    draftMarker: null,
  })),

  updateMarker: (id, updatedData) => set((state) => ({
    markers: state.markers.map((m) => (m.id === id ? { ...m, ...updatedData } : m)),
  })),

  deleteMarker: (id) => set((state) => ({
    markers: state.markers.filter((m) => m.id !== id),
    activeMarkerId: state.activeMarkerId === id ? null : state.activeMarkerId,
  })),

  setActiveMarker: (id) => set({ activeMarkerId: id, draftMarker: null }),

  reset: () => set({ ...initialState }),
}));

export default useMapStore;
