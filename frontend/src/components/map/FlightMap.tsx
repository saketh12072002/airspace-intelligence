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
import { MapStyleSelector, MAP_STYLES, type MapTheme } from '@/components/ui/MapStyleSelector';
import { AltitudeLegend } from '@/components/ui/AltitudeLegend';
import type { Aircraft, FlightRoute } from '@/types';

/**
 * Dark aviation map style default.
 */
const DEFAULT_MAP_STYLE = MAP_STYLES.dark.url;

/** Centre of the world for global overview */
const WORLD_CENTER: [number, number] = [15.0, 20.0];
const WORLD_ZOOM = 1.8;

/** Centre of India for regional view */
const INDIA_CENTER: [number, number] = [78.9629, 20.5937];
const INDIA_ZOOM = 4.5;

const FlightMap: React.FC = () => {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const [mapReady, setMapReady] = useState(false);
  const [mapTheme, setMapTheme] = useState<MapTheme>('dark');

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
      style: DEFAULT_MAP_STYLE,
      center: WORLD_CENTER,
      zoom: WORLD_ZOOM,
      attributionControl: false,
      maxZoom: 18,
      minZoom: 1.0,
      renderWorldCopies: true,
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

  // ── Viewport Preset Handlers ─────────────────────────────────────
  const handleFlyToWorld = useCallback(() => {
    mapRef.current?.flyTo({
      center: WORLD_CENTER,
      zoom: WORLD_ZOOM,
      duration: 1500,
    });
  }, []);

  const handleFlyToIndia = useCallback(() => {
    mapRef.current?.flyTo({
      center: INDIA_CENTER,
      zoom: INDIA_ZOOM,
      duration: 1500,
    });
  }, []);

  // ── Map style switcher ─────────────────────────────────────────
  const handleThemeChange = useCallback((newTheme: MapTheme) => {
    setMapTheme(newTheme);
    if (mapRef.current) {
      mapRef.current.setStyle(MAP_STYLES[newTheme].url);
    }
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

        {/* Map Theme / Style Switcher */}
        <MapStyleSelector currentTheme={mapTheme} onThemeChange={handleThemeChange} />

        {/* Dynamic Altitude Spectrum Legend */}
        <AltitudeLegend />

        {/* Viewport Presets (Global World View & India View) */}
        <div className="absolute bottom-24 right-3 z-40 flex flex-col gap-1.5 shadow-xl">
          <button
            onClick={handleFlyToWorld}
            className="flex items-center gap-1.5 bg-gray-900/90 hover:bg-gray-800 text-gray-200 border border-gray-700/80 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-all shadow-md backdrop-blur-sm hover:border-cyan-500/50"
            title="Fit All Global Flights"
          >
            <span className="text-sm">🌍</span>
            <span>World</span>
          </button>
          <button
            onClick={handleFlyToIndia}
            className="flex items-center gap-1.5 bg-gray-900/90 hover:bg-gray-800 text-gray-200 border border-gray-700/80 rounded-lg px-2.5 py-1.5 text-xs font-medium transition-all shadow-md backdrop-blur-sm hover:border-amber-500/50"
            title="Recenter on India"
          >
            <span className="text-sm">🇮🇳</span>
            <span>India</span>
          </button>
        </div>

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
