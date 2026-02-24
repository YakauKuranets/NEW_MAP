import { useEffect, useMemo, useRef, useState } from 'react';
import { booleanPointInPolygon, point } from '@turf/turf';

const toNumber = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

const resolveAgentId = (agent, lon, lat) => String(agent.agent_id ?? agent.id ?? agent.user_id ?? agent.vendor ?? `${lon},${lat}`);

export default function useGeofenceMonitor(activeAgents, geofences) {
  const [violatingAgentIds, setViolatingAgentIds] = useState([]);
  const [alerts, setAlerts] = useState([]);
  const previousViolationSetRef = useRef(new Set());

  const polygons = useMemo(() => {
    const list = geofences?.features || [];
    return list.filter((feature) => feature?.geometry?.type === 'Polygon' || feature?.geometry?.type === 'MultiPolygon');
  }, [geofences]);

  useEffect(() => {
    const violations = (activeAgents || [])
      .map((agent) => {
        const lon = toNumber(agent.lon ?? agent.longitude);
        const lat = toNumber(agent.lat ?? agent.latitude);
        if (lon === null || lat === null) return null;

        const isInside = polygons.some((zone) => booleanPointInPolygon(point([lon, lat]), zone));
        if (!isInside) return null;

        return {
          id: resolveAgentId(agent, lon, lat),
          name: agent.name || agent.vendor || `ID ${resolveAgentId(agent, lon, lat)}`,
        };
      })
      .filter(Boolean);

    const violationIds = violations.map((item) => item.id);
    const nowSet = new Set(violationIds);
    const previousSet = previousViolationSetRef.current;

    const nextAlerts = violations
      .filter((item) => !previousSet.has(item.id))
      .map((item) => ({
        id: `${item.id}:${Date.now()}`,
        message: `⚠️ Тревога: Агент ${item.name} нарушил периметр!`,
      }));

    previousViolationSetRef.current = nowSet;
    setViolatingAgentIds(violationIds);
    if (nextAlerts.length) setAlerts((prev) => [...nextAlerts, ...prev].slice(0, 8));
  }, [activeAgents, polygons]);

  return { violatingAgentIds, alerts };
}
