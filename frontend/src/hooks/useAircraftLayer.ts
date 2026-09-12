'use client';

import { useEffect, useRef } from 'react';
import maplibregl, { type Map as MapLibreMap } from 'maplibre-gl';
import type { Aircraft, AircraftFeatureCollection } from '@/types';

const SOURCE_ID = 'aircraft-source';
const LAYER_ID = 'aircraft-layer';
const AIRCRAFT_IMAGE_ID = 'aircraft-icon';

/**
 * Airplane icon as an inline SVG data URL.
 * A simple top-down silhouette pointing north (0°).  MapLibre's
 * `icon-rotate` property will rotate it to match `true_track`.
 */
const AIRCRAFT_SVG = `<svg xmlns="http://www.w3.org/2000/svg" width="32" height="32" viewBox="0 0 32 32">
  <path d="M16 2 L19 12 L28 14 L19 16 L19 26 L22 28 L16 30 L10 28 L13 26 L13 16 L4 14 L13 12 Z"
        fill="#00e5ff" stroke="#004d5e" stroke-width="0.8"/>
</svg>`;

/**
 * Hook that manages a MapLibre GeoJSON source + symbol layer for
 * rendering aircraft.  Updates the source data each time `version`
 * changes (driven by the WebSocket hook).
 *
 * This approach renders thousands of aircraft in a single GPU-backed
 * layer instead of creating individual DOM elements.
 */
export function useAircraftLayer(
  map: MapLibreMap | null,
  aircraftRef: React.RefObject<Map<string, Aircraft>>,
  version: number,
  onAircraftClick: (icao24: string) => void,
) {
  const layerReady = useRef(false);
  const prevVersion = useRef(-1);

  // ── Initialise source + layer once the map style loads ──────────
  useEffect(() => {
    if (!map) return;

    const setup = () => {
      if (layerReady.current) return;

      // Load the airplane icon image
      const img = new Image(32, 32);
      img.onload = () => {
        if (!map.hasImage(AIRCRAFT_IMAGE_ID)) {
          map.addImage(AIRCRAFT_IMAGE_ID, img, { sdf: false });
        }

        // Add GeoJSON source (initially empty)
        if (!map.getSource(SOURCE_ID)) {
          map.addSource(SOURCE_ID, {
            type: 'geojson',
            data: { type: 'FeatureCollection', features: [] },
          });
        }

        // Add the symbol layer
        if (!map.getLayer(LAYER_ID)) {
          map.addLayer({
            id: LAYER_ID,
            type: 'symbol',
            source: SOURCE_ID,
            layout: {
              'icon-image': AIRCRAFT_IMAGE_ID,
              'icon-size': [
                'interpolate', ['linear'], ['zoom'],
                3, 0.4,
                6, 0.6,
                10, 0.9,
              ],
              'icon-rotate': ['get', 'rotation'],
              'icon-rotation-alignment': 'map',
              'icon-allow-overlap': true,
              'icon-ignore-placement': true,
              'text-field': ['step', ['zoom'], '', 7, ['get', 'callsign']],
              'text-font': ['Open Sans Regular'],
              'text-size': 10,
              'text-offset': [0, 1.5],
              'text-anchor': 'top',
              'text-optional': true,
            },
            paint: {
              'icon-opacity': 0.95,
              'text-color': '#a0e5ff',
              'text-halo-color': '#000000',
              'text-halo-width': 1,
            },
          });
        }

        layerReady.current = true;
      };
      img.src = `data:image/svg+xml;charset=utf-8,${encodeURIComponent(AIRCRAFT_SVG)}`;
    };

    if (map.isStyleLoaded()) {
      setup();
    } else {
      map.on('load', setup);
    }

    return () => {
      map.off('load', setup);
    };
  }, [map]);

  // ── Click handler ───────────────────────────────────────────────
  useEffect(() => {
    if (!map) return;

    const handleClick = (e: maplibregl.MapLayerMouseEvent) => {
      const feature = e.features?.[0];
      if (feature?.properties?.icao24) {
        onAircraftClick(feature.properties.icao24);
      }
    };

    const handleMouseEnter = () => {
      if (map.getCanvas()) map.getCanvas().style.cursor = 'pointer';
    };

    const handleMouseLeave = () => {
      if (map.getCanvas()) map.getCanvas().style.cursor = '';
    };

    map.on('click', LAYER_ID, handleClick);
    map.on('mouseenter', LAYER_ID, handleMouseEnter);
    map.on('mouseleave', LAYER_ID, handleMouseLeave);

    return () => {
      map.off('click', LAYER_ID, handleClick);
      map.off('mouseenter', LAYER_ID, handleMouseEnter);
      map.off('mouseleave', LAYER_ID, handleMouseLeave);
    };
  }, [map, onAircraftClick]);

  // ── Update GeoJSON data when version changes ────────────────────
  useEffect(() => {
    if (!map || !layerReady.current || version === prevVersion.current) return;
    prevVersion.current = version;

    const source = map.getSource(SOURCE_ID) as maplibregl.GeoJSONSource | undefined;
    if (!source) return;

    const aircraft = aircraftRef.current;
    if (!aircraft) return;

    const features: AircraftFeatureCollection['features'] = [];
    aircraft.forEach((ac) => {
      if (ac.longitude == null || ac.latitude == null) return;
      features.push({
        type: 'Feature',
        geometry: {
          type: 'Point',
          coordinates: [ac.longitude, ac.latitude],
        },
        properties: {
          icao24: ac.icao24,
          callsign: ac.callsign?.trim() || ac.icao24,
          rotation: ac.true_track ?? 0,
          altitude: ac.baro_altitude ?? 0,
          velocity: ac.velocity ?? 0,
          on_ground: ac.on_ground,
        },
      });
    });

    source.setData({ type: 'FeatureCollection', features });
  }, [map, version, aircraftRef]);
}
