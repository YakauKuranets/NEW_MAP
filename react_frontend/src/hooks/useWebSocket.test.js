import React from 'react';
import { act } from 'react-dom/test-utils';
import { createRoot } from 'react-dom/client';
import useMapStore from '../store/useMapStore';
import useWebSocket from './useWebSocket';

function TestHarness({ wsFactory }) {
  useWebSocket({ url: 'ws://test', wsFactory });
  return React.createElement('div', null, 'ok');
}

describe('useWebSocket', () => {
  let container;
  let root;

  beforeEach(() => {
    useMapStore.getState().reset();
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => {
      root.unmount();
    });
    container.remove();
  });

  test('updates Zustand store on telemetry_update and pending_created events', () => {
    const socket = {
      onmessage: null,
      close: jest.fn(),
    };
    const wsFactory = jest.fn(() => socket);

    act(() => {
      root.render(React.createElement(TestHarness, { wsFactory }));
    });

    act(() => {
      socket.onmessage({
        data: JSON.stringify({
          event: 'telemetry_update',
          data: { agent_id: 'u-1', lat: 53.95, lon: 27.59, heading: 80 },
        }),
      });

      socket.onmessage({
        data: JSON.stringify({
          event: 'pending_created',
          data: { id: 101, lat: 53.9, lon: 27.56, category: 'Охрана', status: 'pending' },
        }),
      });
    });

    const state = useMapStore.getState();
    expect(state.agents['u-1']).toEqual(expect.objectContaining({ lat: 53.95, lon: 27.59, heading: 80 }));
    expect(state.incidents).toEqual([
      expect.objectContaining({ id: 101, status: 'pending' }),
    ]);

    act(() => {
      root.unmount();
    });
    expect(socket.close).toHaveBeenCalled();
  });
});
