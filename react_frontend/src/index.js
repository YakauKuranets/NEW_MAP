import React from 'react';
import { createRoot } from 'react-dom/client';
import maplibregl from 'maplibre-gl';
import { Protocol } from 'pmtiles';
import App from './App';
import './index.css';

const protocol = new Protocol();
maplibregl.addProtocol('pmtiles', protocol.tile);

const container = document.getElementById('root');
const root = createRoot(container);
root.render(<App />);

if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      // ignore service worker registration errors in local/dev contexts
    });
  });
}
