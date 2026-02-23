import React, { useEffect, useMemo, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { ScatterplotLayer } from '@deck.gl/layers';
import Map from 'react-map-gl';
import 'mapbox-gl/dist/mapbox-gl.css';

import useMapStore from '../store/useMapStore';

const INITIAL_VIEW_STATE = {
  longitude: 27.56,
  latitude: 53.9,
  zoom: 11.5,
  pitch: 45,
  bearing: 0,
};

const MAP_STYLE = 'mapbox://styles/mapbox/dark-v11';

const toNumber = (value) => {
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
};

export default function CommandCenterMap({ onUserClick }) {
  const agentsMap = useMapStore((s) => s.agents);
  const incidents = useMapStore((s) => s.incidents);
  const setSelectedObject = useMapStore((s) => s.setSelectedObject);

  const [pulseTick, setPulseTick] = useState(0);

  useEffect(() => {
    let raf = 0;
    let mounted = true;

    const loop = () => {
      if (!mounted) return;
      setPulseTick((x) => (x + 1) % 10_000);
      raf = window.requestAnimationFrame(loop);
    };

    raf = window.requestAnimationFrame(loop);
    return () => {
      mounted = false;
      window.cancelAnimationFrame(raf);
    };
  }, []);

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

  const sosPulse = Math.sin(pulseTick * 0.15) * 0.5 + 0.5;

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
      getFillColor: [255, 216, 77, 180],
      getLineColor: [255, 240, 160, 255],
      lineWidthMinPixels: 1,
      radiusMinPixels: 8,
      radiusMaxPixels: 24,
      transitions: {
        getPosition: 250,
      },
    });

    return [incidentLayer, agentLayer];
  }, [normalizedAgents, normalizedIncidents, sosPulse]);

  return (
    <div className="absolute inset-0">
      <DeckGL
        initialViewState={INITIAL_VIEW_STATE}
        controller
        layers={layers}
        onClick={(info) => {
          if (!info?.object) return;
          setSelectedObject(info.object);
          if (info.object.agent_id && onUserClick) onUserClick(String(info.object.agent_id));
        }}
      >
        <Map
          mapboxAccessToken={process.env.REACT_APP_MAPBOX_TOKEN}
          mapStyle={MAP_STYLE}
          reuseMaps
          dragRotate
        />
      </DeckGL>
    </div>
  );
}
