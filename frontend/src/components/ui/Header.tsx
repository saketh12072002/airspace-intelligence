'use client';

import React from 'react';
import type { ConnectionStatus } from '@/types';
import { formatISOTime } from '@/lib/utils/format';

interface HeaderProps {
  count: number;
  status: ConnectionStatus;
  lastUpdate: string | null;
}

const STATUS_COLORS: Record<ConnectionStatus, string> = {
  connected: 'bg-green-500',
  connecting: 'bg-yellow-500 animate-pulse',
  disconnected: 'bg-red-500',
  error: 'bg-red-600',
};

const STATUS_LABELS: Record<ConnectionStatus, string> = {
  connected: 'LIVE',
  connecting: 'CONNECTING',
  disconnected: 'OFFLINE',
  error: 'ERROR',
};

export const Header: React.FC<HeaderProps> = ({ count, status, lastUpdate }) => {
  return (
    <header className="bg-gray-950/90 backdrop-blur-sm border-b border-gray-800 px-4 py-2 flex items-center justify-between z-50 relative select-none">
      {/* Left — Branding */}
      <div className="flex items-center gap-3">
        <h1 className="text-sm font-bold tracking-widest text-cyan-400 uppercase">
          Airspace Intelligence
        </h1>
        <span
          className={`inline-flex items-center gap-1.5 text-[10px] font-bold tracking-wider px-2 py-0.5 rounded-full ${
            status === 'connected'
              ? 'bg-green-500/20 text-green-400 border border-green-500/30'
              : status === 'connecting'
              ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30'
              : 'bg-red-500/20 text-red-400 border border-red-500/30'
          }`}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${STATUS_COLORS[status]}`} />
          {STATUS_LABELS[status]}
        </span>
      </div>

      {/* Right — Stats */}
      <div className="flex items-center gap-4 text-xs text-gray-400">
        <div className="flex items-center gap-1.5">
          <svg className="w-3.5 h-3.5 text-cyan-500" fill="currentColor" viewBox="0 0 20 20">
            <path d="M10.894 2.553a1 1 0 00-1.788 0l-7 14a1 1 0 001.169 1.409l5-1.429A1 1 0 009 15.571V11a1 1 0 112 0v4.571a1 1 0 00.725.962l5 1.428a1 1 0 001.17-1.408l-7-14z" />
          </svg>
          <span className="font-mono text-gray-200">{count.toLocaleString()}</span>
          <span className="hidden sm:inline">aircraft</span>
        </div>
        {lastUpdate && (
          <div className="hidden sm:flex items-center gap-1.5 text-gray-500">
            <span>Updated</span>
            <span className="font-mono text-gray-400">{formatISOTime(lastUpdate)}</span>
          </div>
        )}
      </div>
    </header>
  );
};
