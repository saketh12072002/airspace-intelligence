/**
 * AircraftMarker is intentionally unused — aircraft are rendered via
 * MapLibre's GeoJSON symbol layer for GPU-backed performance.
 *
 * This file is kept as a reference for future per-aircraft DOM overlays
 * (e.g., popup tooltips).
 */

import React from 'react';
import type { Aircraft } from '@/types';

interface AircraftMarkerProps {
  aircraft: Aircraft;
}

export const AircraftMarker: React.FC<AircraftMarkerProps> = ({ aircraft }) => {
  return (
    <div className="hidden">
      {/* Placeholder — aircraft rendered via MapLibre symbol layer */}
      {aircraft.callsign || aircraft.icao24}
    </div>
  );
};
