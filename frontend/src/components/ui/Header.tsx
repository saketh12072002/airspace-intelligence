'use client';

import React from 'react';
import type { ConnectionStatus } from '@/types';
import { formatISOTime } from '@/lib/utils/format';

interface HeaderProps {
  count: number;
  status: ConnectionStatus;
  lastUpdate: string | null;
}

const STATUS_CONFIG: Record<
  ConnectionStatus,
  { label: string; badgeClass: string; dotClass: string }
> = {
  connected: {
    label: 'RADAR LIVE',
    badgeClass: 'bg-emerald-950/80 text-emerald-300 border-emerald-500/50 shadow-emerald-500/20 shadow-sm',
    dotClass: 'bg-emerald-400 animate-ping',
  },
  connecting: {
    label: 'CONNECTING',
    badgeClass: 'bg-amber-950/80 text-amber-300 border-amber-500/50 shadow-amber-500/20 shadow-sm',
    dotClass: 'bg-amber-400 animate-pulse',
  },
  disconnected: {
    label: 'OFFLINE',
    badgeClass: 'bg-rose-950/80 text-rose-300 border-rose-500/50 shadow-rose-500/20 shadow-sm',
    dotClass: 'bg-rose-500',
  },
  error: {
    label: 'RECONNECTING',
    badgeClass: 'bg-rose-950/80 text-rose-300 border-rose-500/50',
    dotClass: 'bg-rose-500',
  },
};

export const Header: React.FC<HeaderProps> = ({ count, status, lastUpdate }) => {
  const currentStatus = STATUS_CONFIG[status];

  return (
    <header className="bg-gradient-to-r from-gray-950 via-gray-900 to-gray-950 backdrop-blur-md border-b border-gray-800/90 px-4 py-2 flex items-center justify-between z-50 relative select-none shadow-lg">
      {/* Left — Branding with neon gradient */}
      <div className="flex items-center gap-3">
        <div className="flex items-center gap-1.5">
          <div className="w-6 h-6 rounded-lg bg-gradient-to-br from-cyan-400 via-blue-500 to-indigo-600 flex items-center justify-center shadow-cyan-500/30 shadow-md">
            <svg
              className="w-4 h-4 text-white transform rotate-45"
              fill="currentColor"
              viewBox="0 0 24 24"
            >
              <path d="M21 16v-2l-8-5V3.5c0-.83-.67-1.5-1.5-1.5S10 2.67 10 3.5V9l-8 5v2l8-2.5V19l-2 1.5V22l3.5-1 3.5 1v-1.5L13 19v-5.5l8 2.5z" />
            </svg>
          </div>
          <div className="flex items-baseline gap-1.5">
            <span className="text-base font-black tracking-widest bg-gradient-to-r from-cyan-300 via-sky-400 to-blue-400 bg-clip-text text-transparent uppercase font-mono">
              Airspace
            </span>
            <span className="text-base font-black tracking-wider bg-gradient-to-r from-violet-400 via-pink-400 to-amber-400 bg-clip-text text-transparent uppercase font-mono">
              Intelligence
            </span>
          </div>
        </div>

        {/* Live Radar Pulse Badge */}
        <span
          className={`inline-flex items-center gap-2 text-[10px] font-mono font-bold tracking-wider px-2.5 py-0.5 rounded-full border ${currentStatus.badgeClass}`}
        >
          <span className="relative flex h-2 w-2">
            <span
              className={`absolute inline-flex h-full w-full rounded-full opacity-75 ${currentStatus.dotClass}`}
            />
            <span
              className={`relative inline-flex rounded-full h-2 w-2 ${
                status === 'connected' ? 'bg-emerald-400' : 'bg-amber-400'
              }`}
            />
          </span>
          {currentStatus.label}
        </span>
      </div>

      {/* Right — Stats & Telemetry Chips */}
      <div className="flex items-center gap-3 text-xs">
        {/* Colorful Count Chip */}
        <div className="flex items-center gap-2 px-3 py-1 rounded-lg bg-gradient-to-r from-cyan-950/60 via-gray-900 to-indigo-950/60 border border-cyan-800/40 shadow-inner">
          <span className="text-cyan-400 font-bold">✈</span>
          <span className="font-mono font-bold text-transparent bg-gradient-to-r from-cyan-300 to-blue-300 bg-clip-text text-sm">
            {count > 0 ? count.toLocaleString() : '0'}
          </span>
          <span className="hidden sm:inline text-[11px] text-gray-400 font-medium">
            live flights
          </span>
        </div>

        {/* Last updated timestamp */}
        {lastUpdate && (
          <div className="hidden md:flex items-center gap-1.5 text-gray-400 text-[11px] font-mono px-2 py-1 rounded-md bg-gray-900/60 border border-gray-800">
            <span className="text-gray-500">Sync:</span>
            <span className="text-gray-300 font-semibold">{formatISOTime(lastUpdate)}</span>
          </div>
        )}
      </div>
    </header>
  );
};
