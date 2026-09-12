'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { useAircraftWebSocket } from '@/hooks/useAircraftWebSocket';
import { useAircraftLayer } from '@/hooks/useAircraftLayer';
import { useRouteLayer } from '@/hooks/useRouteLayer';
import { Header } from '@/components/ui/Header';
import { SearchBar } from '@/components/ui/SearchBar';
import { StatusOverlay } from '@/components/ui/StatusOverlay';
import { AircraftPanel } from '@/components/aircraft/AircraftPanel';
import type { Aircraft, FlightRoute } from '@/types';

/**
 * Dark aviation map style.
 * CartoDB Dark Matter — free, no API key required.
 */
const MAP_STYLE = 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json';

/** Centre of India for the "recenter" button. */
const INDIA_CENTER: [number, number] = [78.9629, 20.5937];
const INDIA_ZOOM = 4.5;

const FlightMap: React.FC = () => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [mapReady, setMapReady] = useState(false);

  // Aircraft WebSocket state
  const { aircraftRef, version, count, status, lastUpdate, error } = useAircraftWebSocket();

  // Selected aircraft & route
  const [selectedIcao, setSelectedIcao] = useState<string | null>(null);
  const [selectedAircraft, setSelectedAircraft] = useState<Aircraft | null>(null);
  const [selectedRoute, setSelectedRoute] = useState<FlightRoute | null>(null);

  // ── Initialize MapLibre ─────────────────────────────────────────
  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: MAP_STYLE,
      center: INDIA_CENTER,
      zoom: INDIA_ZOOM,
      attributionControl: false,
      maxZoom: 18,
      minZoom: 2,
    });

    map.addControl(new maplibregl.NavigationControl(), 'bottom-right');
    map.addControl(new maplibregl.FullscreenControl(), 'bottom-right');
    map.addControl(
      new maplibregl.AttributionControl({ compact: true }),
      'bottom-left',
    );

    map.on('load', () => {
      setMapReady(true);
    });

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // ── Aircraft click handler ──────────────────────────────────────
  const handleAircraftClick = useCallback((icao24: string) => {
    setSelectedIcao(icao24);
    setSelectedRoute(null);
  }, []);

  // Keep selected aircraft data fresh
  useEffect(() => {
    if (!selectedIcao) {
      setSelectedAircraft(null);
      setSelectedRoute(null);
      return;
    }
    const ac = aircraftRef.current?.get(selectedIcao) ?? null;
    setSelectedAircraft(ac);
  }, [selectedIcao, version, aircraftRef]);

  const handleClosePanel = useCallback(() => {
    setSelectedIcao(null);
    setSelectedAircraft(null);
    setSelectedRoute(null);
  }, []);

  // ── Aircraft layer (GeoJSON source + symbol layer) ──────────────
  useAircraftLayer(
    mapReady ? mapRef.current : null,
    aircraftRef,
    version,
    handleAircraftClick,
  );

  // ── Route layer (Origin -> Aircraft -> Destination path lines) ───
  useRouteLayer(
    mapReady ? mapRef.current : null,
    selectedRoute,
    selectedAircraft,
  );

  // ── Search ──────────────────────────────────────────────────────
  const handleSearch = useCallback(
    (query: string) => {
      if (!query) {
        setSelectedIcao(null);
        return;
      }
      const map = aircraftRef.current;
      if (!map) return;

      // Search by callsign or icao24
      for (const [icao, ac] of map) {
        if (
          icao.toUpperCase().includes(query) ||
          (ac.callsign?.toUpperCase().includes(query))
        ) {
          setSelectedIcao(icao);
          // Fly to the aircraft
          if (ac.longitude != null && ac.latitude != null && mapRef.current) {
            mapRef.current.flyTo({
              center: [ac.longitude, ac.latitude],
              zoom: Math.max(mapRef.current.getZoom(), 8),
              duration: 1500,
            });
          }
          return;
        }
      }
    },
    [aircraftRef],
  );

  // ── Recenter on India ───────────────────────────────────────────
  const handleRecenter = useCallback(() => {
    mapRef.current?.flyTo({
      center: INDIA_CENTER,
      zoom: INDIA_ZOOM,
      duration: 1500,
    });
  }, []);

  return (
    <div className="flex flex-col w-full h-screen bg-gray-950 overflow-hidden">
      {/* Header */}
      <Header count={count} status={status} lastUpdate={lastUpdate} />

      {/* Map container */}
      <div className="relative flex-1 w-full">
        <div ref={mapContainer} className="absolute top-0 left-0 w-full h-full" />

        {/* Search bar */}
        <SearchBar onSearch={handleSearch} />

        {/* Recenter button */}
        <button
          onClick={handleRecenter}
          className="absolute bottom-24 right-3 z-40 bg-gray-900/90 hover:bg-gray-800 border border-gray-700 rounded-lg p-2 transition-colors shadow-lg"
          title="Recenter on India"
        >
          <svg className="w-5 h-5 text-gray-300" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
            />
          </svg>
        </button>

        {/* Aircraft panel */}
        <AircraftPanel
          aircraft={selectedAircraft}
          onClose={handleClosePanel}
          onDetailsLoaded={(details) => setSelectedRoute(details?.route ?? null)}
        />

        {/* Connection status overlay */}
        <StatusOverlay status={status} error={error} />
      </div>
    </div>
  );
};

export default FlightMap;
