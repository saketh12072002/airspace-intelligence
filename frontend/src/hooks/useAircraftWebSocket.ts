'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import type { Aircraft, AircraftUpdateMessage, ConnectionStatus, WSMessage } from '@/types';

const WS_URL = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000';
const RECONNECT_MAX = 10;
const RECONNECT_BASE_MS = 1000;

export interface AircraftWSState {
  /** All currently tracked aircraft keyed by icao24. */
  aircraft: Map<string, Aircraft>;
  /** Number of tracked aircraft. */
  count: number;
  /** WebSocket connection status. */
  status: ConnectionStatus;
  /** ISO timestamp of the last received update. */
  lastUpdate: string | null;
  /** Accumulated error message (if any). */
  error: string | null;
}

/**
 * Hook that manages the /ws/aircraft WebSocket connection and maintains
 * an in-memory Map of all aircraft states.
 *
 * Returns the current aircraft map, connection status, count, and last
 * update timestamp.  The map reference is stable between renders — only
 * the `count` / `lastUpdate` / `status` state values trigger re-renders.
 */
export function useAircraftWebSocket() {
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const [count, setCount] = useState(0);
  const [lastUpdate, setLastUpdate] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // We keep the aircraft map in a ref so updating 10 000 aircraft doesn't
  // cause a React re-render for every single one.  Components that need
  // the data (the map layer) read from the ref directly.
  const aircraftRef = useRef<Map<string, Aircraft>>(new Map());
  // Monotonically increasing "version" that lets consumers know the ref changed.
  const [version, setVersion] = useState(0);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttempt = useRef(0);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;

    const url = `${WS_URL}/aircraft`;
    setStatus('connecting');
    setError(null);

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      reconnectAttempt.current = 0;
      setStatus('connected');
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current) return;
      try {
        const msg: WSMessage = JSON.parse(event.data);
        if (msg.type === 'heartbeat') return;
        if (msg.type === 'aircraft_update') {
          applyUpdate(msg as AircraftUpdateMessage);
        }
      } catch {
        // ignore malformed messages
      }
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      wsRef.current = null;
      setStatus('disconnected');
      scheduleReconnect();
    };

    ws.onerror = () => {
      if (!mountedRef.current) return;
      setError('WebSocket connection error');
      setStatus('error');
      ws.close();
    };
  }, []);

  const applyUpdate = useCallback((msg: AircraftUpdateMessage) => {
    const map = aircraftRef.current;

    for (const ac of msg.added) {
      map.set(ac.icao24, ac);
    }
    for (const ac of msg.updated) {
      map.set(ac.icao24, ac);
    }
    for (const id of msg.removed) {
      map.delete(id);
    }

    setCount(map.size);
    setLastUpdate(msg.timestamp);
    setVersion((v) => v + 1);
  }, []);

  const scheduleReconnect = useCallback(() => {
    if (!mountedRef.current) return;
    if (reconnectAttempt.current >= RECONNECT_MAX) {
      setError('Max reconnection attempts reached');
      return;
    }
    const delay = Math.min(
      RECONNECT_BASE_MS * Math.pow(2, reconnectAttempt.current),
      30_000,
    );
    reconnectAttempt.current += 1;
    reconnectTimer.current = setTimeout(() => {
      connect();
    }, delay);
  }, [connect]);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) {
        wsRef.current.onclose = null; // prevent reconnect on unmount
        wsRef.current.close();
      }
    };
  }, [connect]);

  return {
    aircraftRef,
    version,
    count,
    status,
    lastUpdate,
    error,
  };
}
