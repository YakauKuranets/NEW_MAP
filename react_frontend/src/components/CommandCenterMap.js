import React, { useEffect, useMemo, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer } from '@deck.gl/layers';
import { FlyToInterpolator } from '@deck.gl/core';
import { Map } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';

import useMapStore from '../store/useMapStore';
import { initPmtiles } from '../vendor/pmtilesSetup';

const INITIAL_VIEW_STATE = {
  longitude: 27.56,
  latitude: 53.9,
  zoom: 11.5,
  pitch: 45,
  bearing: 0,
};

const MAP_STYLE = '/map_style_cyberpunk.json';

initPmtiles();

const toNumber = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

export default function CommandCenterMap({ onUserClick, flyToTarget }) {
  const agentsMap = useMapStore((s) => s.agents);
  const incidents = useMapStore((s) => s.incidents);
  const pendingMarkers = useMapStore((s) => s.pendingMarkers);
  const activePendingMarkerId = useMapStore((s) => s.activePendingMarkerId);
  const setSelectedObject = useMapStore((s) => s.setSelectedObject);

  const [currentTime, setCurrentTime] = useState(0);
  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);

  useEffect(() => {
    let raf = 0;
    let mounted = true;

    const loop = () => {
      if (!mounted) return;
      setCurrentTime((x) => (x + 1) % 10_000);
      raf = window.requestAnimationFrame(loop);
    };

    raf = window.requestAnimationFrame(loop);
    return () => {
      mounted = false;
      window.cancelAnimationFrame(raf);
    };
  }, []);

  useEffect(() => {
    if (!flyToTarget) return;
    setViewState((prev) => ({
      ...prev,
      longitude: flyToTarget.lon,
      latitude: flyToTarget.lat,
      zoom: 16,
      transitionInterpolator: new FlyToInterpolator({ speed: 1.2 }),
      transitionDuration: 1000,
    }));
  }, [flyToTarget]);

  const agents = useMemo(() => Object.values(agentsMap || {}), [agentsMap]);

  const normalizedAgents = useMemo(
    () => agents
      .map((agent) => {
        const lon = toNumber(agent.lon ?? agent.longitude);
        const lat = toNumber(agent.lat ?? agent.latitude);
        if (lon === null || lat === null) return null;
        return { ...agent, lon, lat };
      })
      .filter(Boolean),
    [agents],
  );

  const normalizedIncidents = useMemo(
    () => (incidents || [])
      .map((incident) => {
        const lon = toNumber(incident.lon ?? incident.longitude);
        const lat = toNumber(incident.lat ?? incident.latitude);
        if (lon === null || lat === null) return null;
        return { ...incident, lon, lat };
      })
      .filter(Boolean),
    [incidents],
  );

  const normalizedPending = useMemo(
    () => (pendingMarkers || [])
      .map((pending) => {
        const lon = toNumber(pending.lon ?? pending.longitude);
        const lat = toNumber(pending.lat ?? pending.latitude);
        if (lon === null || lat === null) return null;
        return { ...pending, lon, lat };
      })
      .filter(Boolean),
    [pendingMarkers],
  );

  const sosPulse = Math.sin(currentTime * 0.15) * 0.5 + 0.5;
  const pendingPulse = Math.sin(currentTime * 0.09) * 0.5 + 0.5;

  const layers = useMemo(() => {
    const agentLayer = new ScatterplotLayer({
      id: 'agents-layer',
      data: normalizedAgents,
      pickable: true,
      filled: true,
      stroked: true,
      radiusUnits: 'meters',
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => ((String(d.status || '').toLowerCase() === 'sos' || d.sos) ? 130 : 90),
      getFillColor: (d) => ((String(d.status || '').toLowerCase() === 'sos' || d.sos)
        ? [255, 32, 86, Math.round(160 + sosPulse * 95)]
        : [25, 211, 255, 220]),
      getLineColor: (d) => ((String(d.status || '').toLowerCase() === 'sos' || d.sos)
        ? [255, 80, 120, 255]
        : [120, 235, 255, 255]),
      lineWidthMinPixels: 1,
      radiusMinPixels: 5,
      radiusMaxPixels: 18,
      transitions: {
        getPosition: 350,
      },
    });

    const incidentLayer = new ScatterplotLayer({
      id: 'incidents-layer',
      data: normalizedIncidents,
      pickable: true,
      filled: true,
      stroked: true,
      radiusUnits: 'meters',
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 160,
      getFillColor: (d) => (String(d.status || '').toLowerCase() === 'approved' ? [43, 121, 255, 175] : [255, 216, 77, 180]),
      getLineColor: (d) => (String(d.status || '').toLowerCase() === 'approved' ? [110, 168, 255, 255] : [255, 240, 160, 255]),
      lineWidthMinPixels: 1,
      radiusMinPixels: 8,
      radiusMaxPixels: 24,
      transitions: {
        getPosition: 250,
      },
    });

    const pendingLayer = new ScatterplotLayer({
      id: 'pending-layer',
      data: normalizedPending,
      pickable: true,
      filled: true,
      stroked: true,
      radiusUnits: 'meters',
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => {
        const markerId = String(d.id ?? d.pending ?? d.pending_id);
        const isActive = markerId === String(activePendingMarkerId);
        const baseRadius = isActive ? 190 : 150;
        return baseRadius + pendingPulse * 55;
      },
      getFillColor: () => [255, 200, 0, 200],
      getLineColor: () => [255, 200, 0, Math.round(180 + pendingPulse * 75)],
      lineWidthMinPixels: 2,
      radiusMinPixels: 8,
      radiusMaxPixels: 26,
      transitions: {
        getPosition: 250,
      },
    });

    return [incidentLayer, pendingLayer, agentLayer];
  }, [normalizedAgents, normalizedIncidents, normalizedPending, activePendingMarkerId, pendingPulse, sosPulse]);

  return (
    <div className="absolute inset-0">
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState: nextViewState }) => setViewState(nextViewState)}
        controller
        layers={layers}
        onClick={(info) => {
          if (!info?.object) return;
          setSelectedObject(info.object);
          if (info.object.agent_id && onUserClick) onUserClick(String(info.object.agent_id));
        }}
      >
        <Map
          mapStyle={MAP_STYLE}
          reuseMaps
          dragRotate
        />
      </DeckGL>
    </div>
  );
}
