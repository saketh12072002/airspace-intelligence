'use client';
/* eslint-disable @next/next/no-img-element */

import React, { useEffect, useState } from 'react';
import type { Aircraft, FlightDetails } from '@/types';
import {
  formatAltitude,
  formatSpeed,
  formatVerticalRate,
  formatHeading,
  formatCoord,
  formatTimestamp,
  formatCallsign,
} from '@/lib/utils/format';

interface AircraftPanelProps {
  aircraft: Aircraft | null;
  onClose: () => void;
  onDetailsLoaded?: (details: FlightDetails | null) => void;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const AircraftPanel: React.FC<AircraftPanelProps> = ({
  aircraft,
  onClose,
  onDetailsLoaded,
}) => {
  const [details, setDetails] = useState<FlightDetails | null>(null);
  const [loading, setLoading] = useState(false);
  const [showPhoto, setShowPhoto] = useState(false);

  useEffect(() => {
    if (!aircraft) {
      setDetails(null);
      onDetailsLoaded?.(null);
      return;
    }

    let isMounted = true;
    setLoading(true);

    fetch(`${API_BASE_URL}/api/aircraft/${aircraft.icao24}/details`)
      .then((res) => {
        if (!res.ok) throw new Error('Failed to fetch details');
        return res.json();
      })
      .then((data: FlightDetails) => {
        if (isMounted) {
          setDetails(data);
          onDetailsLoaded?.(data);
          setLoading(false);
        }
      })
      .catch((err) => {
        console.warn('Flight details fetch error:', err);
        if (isMounted) {
          setLoading(false);
          onDetailsLoaded?.(null);
        }
      });

    return () => {
      isMounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aircraft?.icao24]);

  if (!aircraft) return null;

  const route = details?.route;
  const meta = details?.metadata;
  const origin = route?.origin;
  const destination = route?.destination;
  const airline = route?.airline;

  const flightNumber =
    route?.callsign_iata ||
    route?.callsign_icao ||
    formatCallsign(aircraft.callsign);

  const airlineName =
    airline?.name ||
    meta?.registered_owner ||
    (aircraft.origin_country ? `${aircraft.origin_country} Operator` : 'Unknown Operator');

  return (
    <div className="absolute top-14 right-3 z-40 w-80 md:w-96 bg-gray-900/95 backdrop-blur-md rounded-xl border border-gray-700/80 shadow-2xl overflow-hidden flex flex-col max-h-[calc(100vh-70px)] transition-all animate-in fade-in slide-in-from-right-2">
      {/* ── Top Header ────────────────────────────────────────────── */}
      <div className="px-4 py-3 bg-gradient-to-r from-gray-900 via-gray-800/80 to-gray-900 border-b border-gray-700/70 flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xl font-bold font-mono text-cyan-400 tracking-wide truncate">
              {flightNumber}
            </span>
            {airline?.iata && (
              <span className="px-1.5 py-0.5 text-[10px] font-bold bg-cyan-950 text-cyan-300 border border-cyan-700/60 rounded">
                {airline.iata}
              </span>
            )}
          </div>
          <p className="text-xs text-gray-300 font-medium truncate mt-0.5">
            {airlineName}
          </p>
          <p className="text-[10px] text-gray-500 font-mono uppercase tracking-wider mt-0.5">
            ICAO: {aircraft.icao24.toUpperCase()} · Callsign: {formatCallsign(aircraft.callsign)}
          </p>
        </div>

        <button
          onClick={onClose}
          className="text-gray-400 hover:text-white transition-colors p-1.5 -mr-1 rounded-lg hover:bg-gray-800"
          aria-label="Close panel"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* ── Scrollable Body ────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4 text-gray-200">
        {/* ── Route Section (Origin -> Destination) ─────────────────── */}
        {origin && destination ? (
          <div className="bg-gradient-to-b from-gray-800/80 via-gray-900/90 to-gray-950 rounded-xl p-3.5 border border-gray-700/60 shadow-xl">
            <div className="flex items-center justify-between text-center gap-2">
              {/* Origin Card */}
              <div className="flex-1 text-left min-w-0 p-2 rounded-lg bg-emerald-950/40 border border-emerald-500/30">
                <span className="text-2xl font-black font-mono text-emerald-300 tracking-tight block">
                  {origin.iata_code || origin.icao_code || 'DEP'}
                </span>
                <p className="text-xs font-semibold text-emerald-100 truncate mt-0.5">
                  {origin.municipality || origin.name || 'Departure'}
                </p>
                <p className="text-[10px] text-emerald-400/80 truncate">
                  {origin.country_name || origin.country_iso || ''}
                </p>
              </div>

              {/* Center Airplane Graphic */}
              <div className="px-1 flex flex-col items-center justify-center">
                <div className="w-8 h-8 rounded-full bg-cyan-950/80 border border-cyan-500/50 flex items-center justify-center shadow-cyan-500/20 shadow-md">
                  <svg
                    className="w-4 h-4 text-cyan-300 transform rotate-90"
                    fill="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z" />
                  </svg>
                </div>
              </div>

              {/* Destination Card */}
              <div className="flex-1 text-right min-w-0 p-2 rounded-lg bg-amber-950/40 border border-amber-500/30">
                <span className="text-2xl font-black font-mono text-amber-300 tracking-tight block">
                  {destination.iata_code || destination.icao_code || 'ARR'}
                </span>
                <p className="text-xs font-semibold text-amber-100 truncate mt-0.5">
                  {destination.municipality || destination.name || 'Arrival'}
                </p>
                <p className="text-[10px] text-amber-400/80 truncate">
                  {destination.country_name || destination.country_iso || ''}
                </p>
              </div>
            </div>

            {/* Flight Progress Bar */}
            {route.progress_percent != null && (
              <div className="mt-3.5 pt-2.5 border-t border-gray-700/50">
                <div className="flex justify-between items-center text-[11px] font-mono text-gray-300 mb-1.5">
                  <span className="font-bold text-cyan-300">{route.progress_percent.toFixed(0)}% Completed</span>
                  {route.total_distance_km && (
                    <span className="text-gray-400">{Math.round(route.total_distance_km)} km total</span>
                  )}
                </div>
                <div className="w-full h-2 bg-gray-950 rounded-full overflow-hidden p-0.5 border border-gray-800">
                  <div
                    className="h-full bg-gradient-to-r from-emerald-400 via-cyan-400 via-blue-500 to-amber-400 rounded-full transition-all duration-500 shadow-cyan-500/50 shadow-sm"
                    style={{ width: `${Math.min(100, Math.max(0, route.progress_percent))}%` }}
                  />
                </div>
                <div className="flex justify-between items-center text-[10px] font-mono text-gray-400 mt-1.5">
                  <span className="text-emerald-400 font-semibold">{route.distance_flown_km ? `${Math.round(route.distance_flown_km)} km flown` : ''}</span>
                  <span className="text-amber-400 font-semibold">{route.distance_remaining_km ? `${Math.round(route.distance_remaining_km)} km remaining` : ''}</span>
                </div>
              </div>
            )}
          </div>
        ) : loading ? (
          <div className="bg-gray-800/40 rounded-lg p-3 border border-gray-800 text-center animate-pulse">
            <p className="text-xs text-cyan-400 font-mono">Resolving flight route & airports…</p>
          </div>
        ) : (
          <div className="bg-gray-800/30 rounded-lg p-2.5 border border-gray-800 text-center">
            <p className="text-xs text-gray-400">Route schedule not filed for callsign</p>
          </div>
        )}

        {/* ── Aircraft Airframe Specifications ────────────────────────── */}
        {(meta?.type || meta?.manufacturer || meta?.registration) && (
          <div className="bg-gray-800/40 rounded-lg p-3 border border-gray-700/40 space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-[11px] font-semibold text-cyan-300 uppercase tracking-wider">
                Aircraft Specifications
              </span>
              {meta.registration && (
                <span className="text-xs font-mono font-bold px-1.5 py-0.5 bg-gray-800 text-yellow-300 border border-yellow-500/30 rounded">
                  {meta.registration}
                </span>
              )}
            </div>

            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-[10px] text-gray-400 block">Model / Type</span>
                <span className="font-medium text-gray-100">
                  {meta.type || meta.icao_type || '—'}
                </span>
              </div>
              <div>
                <span className="text-[10px] text-gray-400 block">Manufacturer</span>
                <span className="font-medium text-gray-100">
                  {meta.manufacturer || '—'}
                </span>
              </div>
            </div>

            {/* Photo Thumbnail */}
            {meta.url_photo_thumbnail && (
              <div className="mt-2 pt-2 border-t border-gray-700/40">
                <img
                  src={meta.url_photo_thumbnail}
                  alt={meta.type || 'Aircraft photo'}
                  className="w-full h-24 object-cover rounded border border-gray-700 cursor-pointer hover:opacity-90 transition-opacity"
                  onClick={() => setShowPhoto(!showPhoto)}
                />
              </div>
            )}
          </div>
        )}

        {/* ── Live Telemetry Grid ───────────────────────────────────── */}
        <div className="space-y-1.5">
          <span className="text-[11px] font-semibold text-gray-400 uppercase tracking-wider block">
            Live ADS-B Telemetry
          </span>

          <div className="grid grid-cols-2 gap-2">
            {/* Altitude */}
            <div className="bg-gradient-to-br from-cyan-950/50 via-gray-900 to-blue-950/30 p-2.5 rounded-lg border border-cyan-800/40 shadow-sm">
              <span className="text-[10px] text-cyan-300/80 font-medium block">Altitude</span>
              <span className="text-sm font-mono font-bold text-cyan-300">
                {formatAltitude(aircraft.baro_altitude)}
              </span>
            </div>

            {/* Ground Speed */}
            <div className="bg-gradient-to-br from-amber-950/50 via-gray-900 to-orange-950/30 p-2.5 rounded-lg border border-amber-800/40 shadow-sm">
              <span className="text-[10px] text-amber-300/80 font-medium block">Ground Speed</span>
              <span className="text-sm font-mono font-bold text-amber-300">
                {formatSpeed(aircraft.velocity)}
              </span>
            </div>

            {/* Heading */}
            <div className="bg-gradient-to-br from-purple-950/50 via-gray-900 to-indigo-950/30 p-2.5 rounded-lg border border-purple-800/40 shadow-sm">
              <span className="text-[10px] text-purple-300/80 font-medium block">Heading (Track)</span>
              <span className="text-sm font-mono font-bold text-purple-200">
                {formatHeading(aircraft.true_track)}
              </span>
            </div>

            {/* Vertical Rate */}
            <div className="bg-gradient-to-br from-emerald-950/50 via-gray-900 to-teal-950/30 p-2.5 rounded-lg border border-emerald-800/40 shadow-sm">
              <span className="text-[10px] text-emerald-300/80 font-medium block">Vertical Rate</span>
              <span className={`text-sm font-mono font-bold ${
                (aircraft.vertical_rate ?? 0) > 0.5
                  ? 'text-emerald-300'
                  : (aircraft.vertical_rate ?? 0) < -0.5
                  ? 'text-rose-400'
                  : 'text-gray-200'
              }`}>
                {formatVerticalRate(aircraft.vertical_rate)}
              </span>
            </div>

            {/* Squawk */}
            <div className="bg-gray-800/50 p-2.5 rounded-lg border border-gray-700/40">
              <span className="text-[10px] text-gray-400 block">Squawk</span>
              <span className="text-sm font-mono text-yellow-300 font-bold">
                {aircraft.squawk || '—'}
              </span>
            </div>

            {/* Last Contact */}
            <div className="bg-gray-800/50 p-2.5 rounded-lg border border-gray-700/40">
              <span className="text-[10px] text-gray-400 block">Radar Contact</span>
              <span className="text-sm font-mono text-gray-200">
                {formatTimestamp(aircraft.last_contact)}
              </span>
            </div>
          </div>

          {/* Coordinates */}
          <div className="bg-gray-800/30 p-2 rounded border border-gray-800 flex justify-between text-[11px] font-mono text-gray-400">
            <span>Lat: {formatCoord(aircraft.latitude)}</span>
            <span>Lon: {formatCoord(aircraft.longitude)}</span>
          </div>
        </div>
      </div>

      {/* ── Footer ─────────────────────────────────────────────────── */}
      <div className="px-4 py-2.5 bg-gray-900/90 border-t border-gray-800 flex items-center justify-between text-xs">
        <span
          className={`inline-flex items-center gap-1.5 font-medium ${
            aircraft.on_ground
              ? 'text-yellow-400'
              : (aircraft.baro_altitude ?? 0) > 10000
              ? 'text-cyan-400'
              : 'text-green-400'
          }`}
        >
          <span
            className={`w-2 h-2 rounded-full animate-pulse ${
              aircraft.on_ground ? 'bg-yellow-400' : 'bg-green-400'
            }`}
          />
          {aircraft.on_ground ? 'On Ground' : 'In Flight'}
        </span>

        <span className="text-[10px] text-gray-500 font-mono">
          Airspace Intelligence
        </span>
      </div>
    </div>
  );
};
