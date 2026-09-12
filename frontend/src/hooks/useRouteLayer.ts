'use client';

import { useEffect, useRef } from 'react';
import type { Map as MapLibreMap, GeoJSONSource } from 'maplibre-gl';
import type { Aircraft, FlightRoute } from '@/types';

const ROUTE_SOURCE_FLOWN = 'route-source-flown';
const ROUTE_LAYER_FLOWN = 'route-layer-flown';
const ROUTE_LAYER_FLOWN_GLOW = 'route-layer-flown-glow';

const ROUTE_SOURCE_REMAINING = 'route-source-remaining';
const ROUTE_LAYER_REMAINING = 'route-layer-remaining';

const WAYPOINTS_SOURCE = 'route-waypoints-source';
const WAYPOINTS_LAYER_CIRCLE = 'route-waypoints-circle';
const WAYPOINTS_LAYER_TEXT = 'route-waypoints-text';

/** Generate intermediate points along a great-circle path for smooth curved rendering. */
function createArc(start: [number, number], end: [number, number], segments = 50): [number, number][] {
  const [lon1, lat1] = start;
  const [lon2, lat2] = end;

  // Simple interpolation that wraps gracefully
  const coords: [number, number][] = [];
  for (let i = 0; i <= segments; i++) {
    const t = i / segments;
    const lat = lat1 + (lat2 - lat1) * t;
    const lon = lon1 + (lon2 - lon1) * t;
    coords.push([lon, lat]);
  }
  return coords;
}

export function useRouteLayer(
  map: MapLibreMap | null,
  route: FlightRoute | null,
  aircraft: Aircraft | null,
) {
  const layersReady = useRef(false);

  // Setup layers on map load
  useEffect(() => {
    if (!map) return;

    const setup = () => {
      if (layersReady.current) return;

      // 1. Source & Layer: Flown segment (Origin -> Aircraft)
      if (!map.getSource(ROUTE_SOURCE_FLOWN)) {
        map.addSource(ROUTE_SOURCE_FLOWN, {
          type: 'geojson',
          data: { type: 'FeatureCollection', features: [] },
        });
      }

      if (!map.getLayer(ROUTE_LAYER_FLOWN_GLOW)) {
        map.addLayer({
          id: ROUTE_LAYER_FLOWN_GLOW,
          type: 'line',
          source: ROUTE_SOURCE_FLOWN,
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: {
            'line-color': '#00e5ff',
            'line-width': 6,
            'line-opacity': 0.35,
          },
        });
      }

      if (!map.getLayer(ROUTE_LAYER_FLOWN)) {
        map.addLayer({
          id: ROUTE_LAYER_FLOWN,
          type: 'line',
          source: ROUTE_SOURCE_FLOWN,
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: {
            'line-color': '#00e5ff',
            'line-width': 3,
            'line-opacity': 0.95,
          },
        });
      }

      // 2. Source & Layer: Remaining segment (Aircraft -> Destination)
      if (!map.getSource(ROUTE_SOURCE_REMAINING)) {
        map.addSource(ROUTE_SOURCE_REMAINING, {
          type: 'geojson',
          data: { type: 'FeatureCollection', features: [] },
        });
      }

      if (!map.getLayer(ROUTE_LAYER_REMAINING)) {
        map.addLayer({
          id: ROUTE_LAYER_REMAINING,
          type: 'line',
          source: ROUTE_SOURCE_REMAINING,
          layout: { 'line-cap': 'round', 'line-join': 'round' },
          paint: {
            'line-color': '#7dd3fc',
            'line-width': 2.5,
            'line-dasharray': [3, 2.5],
            'line-opacity': 0.8,
          },
        });
      }

      // 3. Waypoints: Origin and Destination markers
      if (!map.getSource(WAYPOINTS_SOURCE)) {
        map.addSource(WAYPOINTS_SOURCE, {
          type: 'geojson',
          data: { type: 'FeatureCollection', features: [] },
        });
      }

      if (!map.getLayer(WAYPOINTS_LAYER_CIRCLE)) {
        map.addLayer({
          id: WAYPOINTS_LAYER_CIRCLE,
          type: 'circle',
          source: WAYPOINTS_SOURCE,
          paint: {
            'circle-radius': 6,
            'circle-color': ['get', 'color'],
            'circle-stroke-width': 2,
            'circle-stroke-color': '#ffffff',
          },
        });
      }

      if (!map.getLayer(WAYPOINTS_LAYER_TEXT)) {
        map.addLayer({
          id: WAYPOINTS_LAYER_TEXT,
          type: 'symbol',
          source: WAYPOINTS_SOURCE,
          layout: {
            'text-field': ['get', 'code'],
            'text-font': ['Open Sans Regular'],
            'text-size': 11,
            'text-offset': [0, 1.4],
            'text-anchor': 'top',
          },
          paint: {
            'text-color': '#ffffff',
            'text-halo-color': '#000000',
            'text-halo-width': 1.5,
          },
        });
      }

      layersReady.current = true;
    };

    if (map.isStyleLoaded()) {
      setup();
    } else {
      map.once('styledata', setup);
    }
  }, [map]);

  // Update route data whenever selected route or aircraft coordinates change
  useEffect(() => {
    if (!map || !layersReady.current) return;

    const flownSource = map.getSource(ROUTE_SOURCE_FLOWN) as GeoJSONSource | undefined;
    const remainingSource = map.getSource(ROUTE_SOURCE_REMAINING) as GeoJSONSource | undefined;
    const waypointsSource = map.getSource(WAYPOINTS_SOURCE) as GeoJSONSource | undefined;

    const clearAll = () => {
      flownSource?.setData({ type: 'FeatureCollection', features: [] });
      remainingSource?.setData({ type: 'FeatureCollection', features: [] });
      waypointsSource?.setData({ type: 'FeatureCollection', features: [] });
    };

    if (!route || !route.origin || !route.destination) {
      clearAll();
      return;
    }

    const { origin, destination } = route;
    if (
      origin.latitude == null ||
      origin.longitude == null ||
      destination.latitude == null ||
      destination.longitude == null
    ) {
      clearAll();
      return;
    }

    const originCoord: [number, number] = [origin.longitude, origin.latitude];
    const destCoord: [number, number] = [destination.longitude, destination.latitude];

    const currentCoord: [number, number] =
      aircraft && aircraft.longitude != null && aircraft.latitude != null
        ? [aircraft.longitude, aircraft.latitude]
        : originCoord;

    // Flown line (Origin -> Current)
    const flownCoords = createArc(originCoord, currentCoord, 30);
    flownSource?.setData({
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: { type: 'LineString', coordinates: flownCoords },
          properties: {},
        },
      ],
    });

    // Remaining line (Current -> Destination)
    const remainingCoords = createArc(currentCoord, destCoord, 30);
    remainingSource?.setData({
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: { type: 'LineString', coordinates: remainingCoords },
          properties: {},
        },
      ],
    });

    // Waypoints
    waypointsSource?.setData({
      type: 'FeatureCollection',
      features: [
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: originCoord },
          properties: {
            code: origin.iata_code || origin.icao_code || 'DEP',
            color: '#22c55e', // Green for departure
          },
        },
        {
          type: 'Feature',
          geometry: { type: 'Point', coordinates: destCoord },
          properties: {
            code: destination.iata_code || destination.icao_code || 'ARR',
            color: '#f97316', // Orange for arrival
          },
        },
      ],
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [map, route, aircraft?.latitude, aircraft?.longitude]);
}
