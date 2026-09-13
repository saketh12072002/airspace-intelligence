'use client';

import React, { useState } from 'react';

const ALTITUDE_STOPS = [
  { label: 'Ground', color: '#f59e0b', desc: 'Taxi / Runway' },
  { label: '0 - 10k ft', color: '#10b981', desc: 'Climb / Approach' },
  { label: '10k - 20k ft', color: '#06b6d4', desc: 'Low Cruise' },
  { label: '20k - 30k ft', color: '#3b82f6', desc: 'Mid Cruise' },
  { label: '30k - 38k ft', color: '#8b5cf6', desc: 'Standard Cruise' },
  { label: '38k+ ft', color: '#ec4899', desc: 'High Flight Level' },
];

export const AltitudeLegend: React.FC = () => {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="absolute bottom-6 left-3 z-30 transition-all duration-300">
      <div className="bg-gray-900/90 backdrop-blur-md border border-gray-700/80 rounded-xl shadow-2xl p-2.5 max-w-xs text-gray-200">
        <div
          className="flex items-center justify-between gap-2 cursor-pointer select-none"
          onClick={() => setExpanded(!expanded)}
        >
          <div className="flex items-center gap-1.5">
            <div className="w-2.5 h-2.5 rounded-full bg-gradient-to-r from-emerald-400 via-cyan-400 via-blue-500 via-purple-500 to-pink-500 animate-pulse" />
            <span className="text-[11px] font-bold tracking-wider uppercase text-cyan-300">
              Altitude Spectrum
            </span>
          </div>

          <button
            className="text-gray-400 hover:text-gray-200 text-xs px-1"
            aria-label="Toggle legend details"
          >
            {expanded ? '▲' : '▼'}
          </button>
        </div>

        {/* Mini Rainbow Bar preview */}
        <div className="mt-2 h-1.5 w-full rounded-full bg-gradient-to-r from-amber-500 via-emerald-400 via-cyan-400 via-blue-500 via-purple-500 to-pink-500" />

        {/* Expanded detailed legend */}
        {expanded && (
          <div className="mt-3 space-y-1.5 pt-2 border-t border-gray-800 text-[11px] animate-in fade-in duration-200">
            {ALTITUDE_STOPS.map((stop) => (
              <div key={stop.label} className="flex items-center justify-between gap-3">
                <div className="flex items-center gap-2">
                  <span
                    className="w-2.5 h-2.5 rounded-full flex-shrink-0 shadow-sm"
                    style={{ backgroundColor: stop.color }}
                  />
                  <span className="font-mono font-semibold text-gray-200">{stop.label}</span>
                </div>
                <span className="text-[10px] text-gray-400 font-sans">{stop.desc}</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};
