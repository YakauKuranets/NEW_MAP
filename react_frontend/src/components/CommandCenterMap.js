import React, { useEffect, useMemo, useState } from 'react';
import DeckGL from '@deck.gl/react';
import { IconLayer, TextLayer } from '@deck.gl/layers';
import { FlyToInterpolator, WebMercatorViewport } from '@deck.gl/core';
import { Map } from 'react-map-gl/maplibre';
import 'maplibre-gl/dist/maplibre-gl.css';

import useMapStore from '../store/useMapStore';
import useMapClusters from '../hooks/useMapClusters';
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

const isViolationAgent = (agent) => Boolean(
  agent?.isViolation
  || agent?.violation
  || agent?.in_violation
  || agent?.zone_violation
  || agent?.inside_polygon,
);

const svgIcon = (fill, stroke = '#ffffff') => `data:image/svg+xml;utf8,${encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64"><circle cx="32" cy="32" r="20" fill="${fill}" stroke="${stroke}" stroke-width="4" /></svg>`,
)}`;

const ICONS = {
  cluster: { url: svgIcon('#334155', '#e2e8f0'), width: 64, height: 64, anchorY: 32 },
  agent: { url: svgIcon('#19d3ff', '#78ebff'), width: 64, height: 64, anchorY: 32 },
  danger: { url: svgIcon('#ef4444', '#fecaca'), width: 64, height: 64, anchorY: 32 },
  incident: { url: svgIcon('#f59e0b', '#fef3c7'), width: 64, height: 64, anchorY: 32 },
  pending: { url: svgIcon('#fde047', '#fef9c3'), width: 64, height: 64, anchorY: 32 },
  camera: { url: svgIcon('#a78bfa', '#ddd6fe'), width: 64, height: 64, anchorY: 32 },
  unknown: { url: svgIcon('#64748b', '#cbd5e1'), width: 64, height: 64, anchorY: 32 },
};

export default function CommandCenterMap({ onUserClick, flyToTarget, filters }) {
  const effectiveFilters = filters || {
    showAgents: true,
    showCameras: true,
    showIncidents: true,
    showPending: true,
  };
  const agentsMap = useMapStore((s) => s.agents);
  const incidents = useMapStore((s) => s.incidents);
  const pendingMarkers = useMapStore((s) => s.pendingMarkers);
  const markers = useMapStore((s) => s.markers);
  const setSelectedObject = useMapStore((s) => s.setSelectedObject);

  const [pulseTick, setPulseTick] = useState(0);
  const [viewState, setViewState] = useState(INITIAL_VIEW_STATE);
  const [viewportSize, setViewportSize] = useState({ width: window.innerWidth, height: window.innerHeight });

  useEffect(() => {
    const onResize = () => setViewportSize({ width: window.innerWidth, height: window.innerHeight });
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

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

  useEffect(() => {
    if (!flyToTarget) return;
    setViewState((prev) => ({
      ...prev,
      longitude: flyToTarget.lon,
      latitude: flyToTarget.lat,
      zoom: Math.max(prev.zoom, 14.5),
      transitionInterpolator: new FlyToInterpolator({ speed: 1.2 }),
      transitionDuration: 900,
    }));
  }, [flyToTarget]);

  const normalizedAgents = useMemo(
    () => Object.values(agentsMap || {})
      .map((agent) => {
        const lon = toNumber(agent.lon ?? agent.longitude);
        const lat = toNumber(agent.lat ?? agent.latitude);
        if (lon === null || lat === null) return null;
        return {
          ...agent,
          lon,
          lat,
          type: isViolationAgent(agent) ? 'danger' : 'agent',
        };
      })
      .filter(Boolean),
    [agentsMap],
  );

  const normalizedIncidents = useMemo(
    () => (incidents || [])
      .map((incident) => {
        const lon = toNumber(incident.lon ?? incident.longitude);
        const lat = toNumber(incident.lat ?? incident.latitude);
        if (lon === null || lat === null) return null;
        return { ...incident, lon, lat, type: 'incident' };
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
        return { ...pending, lon, lat, type: 'pending' };
      })
      .filter(Boolean),
    [pendingMarkers],
  );

  const normalizedCameras = useMemo(
    () => (markers || [])
      .map((camera) => {
        const lon = toNumber(camera.lon ?? camera.longitude);
        const lat = toNumber(camera.lat ?? camera.latitude);
        if (lon === null || lat === null) return null;
        return { ...camera, lon, lat, type: 'camera' };
      })
      .filter(Boolean),
    [markers],
  );

  const filteredData = useMemo(() => ([
    ...(effectiveFilters.showAgents ? normalizedAgents : []),
    ...(effectiveFilters.showCameras ? normalizedCameras : []),
    ...(effectiveFilters.showIncidents ? normalizedIncidents : []),
    ...(effectiveFilters.showPending ? normalizedPending : []),
  ]), [effectiveFilters, normalizedAgents, normalizedCameras, normalizedIncidents, normalizedPending]);

  const bounds = useMemo(() => {
    try {
      const viewport = new WebMercatorViewport({
        ...viewState,
        width: viewportSize.width,
        height: viewportSize.height,
      });
      return viewport.getBounds();
    } catch (_e) {
      return null;
    }
  }, [viewState, viewportSize]);

  const clusteredData = useMapClusters({
    data: filteredData,
    zoom: viewState.zoom,
    bounds,
  });

  const sosPulse = Math.sin(pulseTick * 0.15) * 0.5 + 0.5;

  const layers = useMemo(() => {
    const iconLayer = new IconLayer({
      id: 'clustered-icon-layer',
      data: clusteredData,
      pickable: true,
      sizeScale: 1,
      getPosition: (d) => d.geometry.coordinates,
      getIcon: (d) => {
        if (d.properties.cluster) return ICONS.cluster;
        const key = d.properties.entityType;
        return ICONS[key] || ICONS.unknown;
      },
      getSize: (d) => {
        if (d.properties.cluster) {
          const count = d.properties.point_count || 1;
          return Math.min(36 + Math.log2(count) * 10, 76);
        }
        if (d.properties.entityType === 'danger') return 42 + sosPulse * 8;
        return 30;
      },
      sizeUnits: 'pixels',
      transitions: {
        getPosition: 300,
      },
    });

    const clusterLabelLayer = new TextLayer({
      id: 'cluster-count-layer',
      data: clusteredData.filter((d) => d.properties.cluster),
      pickable: false,
      billboard: true,
      getPosition: (d) => d.geometry.coordinates,
      getText: (d) => String(d.properties.point_count || ''),
      getColor: [255, 255, 255, 255],
      getSize: 16,
      getTextAnchor: 'middle',
      getAlignmentBaseline: 'center',
      characterSet: 'auto',
      sizeUnits: 'pixels',
      fontSettings: {
        fontWeight: 800,
      },
    });

    return [iconLayer, clusterLabelLayer];
  }, [clusteredData, sosPulse]);

  return (
    <div className="absolute inset-0">
      <DeckGL
        viewState={viewState}
        onViewStateChange={({ viewState: nextViewState }) => setViewState(nextViewState)}
        controller
        layers={layers}
        onClick={(info) => {
          if (!info?.object) return;
          const feature = info.object;
          if (feature?.properties?.cluster) {
            const [lon, lat] = feature.geometry.coordinates;
            setViewState((prev) => ({
              ...prev,
              longitude: lon,
              latitude: lat,
              zoom: Math.min((prev.zoom || 0) + 2, 16),
              transitionInterpolator: new FlyToInterpolator({ speed: 1.3 }),
              transitionDuration: 500,
            }));
            return;
          }

          const selected = feature.properties || null;
          setSelectedObject(selected);
          if (selected?.agent_id && onUserClick) onUserClick(String(selected.agent_id));
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
