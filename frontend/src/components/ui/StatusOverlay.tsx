'use client';

import React from 'react';
import type { ConnectionStatus } from '@/types';

interface StatusOverlayProps {
  status: ConnectionStatus;
  error: string | null;
}

export const StatusOverlay: React.FC<StatusOverlayProps> = ({ status, error }) => {
  if (status === 'connected') return null;

  return (
    <div className="absolute inset-0 z-30 flex items-center justify-center pointer-events-none">
      <div className="bg-gray-900/80 backdrop-blur-md rounded-xl border border-gray-700 px-8 py-6 text-center shadow-2xl pointer-events-auto max-w-sm">
        {status === 'connecting' && (
          <>
            <div className="w-8 h-8 border-2 border-cyan-500 border-t-transparent rounded-full animate-spin mx-auto mb-3" />
            <p className="text-gray-200 font-medium">Connecting to server…</p>
            <p className="text-gray-500 text-sm mt-1">Establishing WebSocket connection</p>
          </>
        )}
        {status === 'disconnected' && (
          <>
            <div className="w-8 h-8 rounded-full bg-yellow-500/20 border border-yellow-500/40 flex items-center justify-center mx-auto mb-3">
              <span className="text-yellow-400 text-lg">⚡</span>
            </div>
            <p className="text-gray-200 font-medium">Connection lost</p>
            <p className="text-gray-500 text-sm mt-1">Reconnecting automatically…</p>
          </>
        )}
        {status === 'error' && (
          <>
            <div className="w-8 h-8 rounded-full bg-red-500/20 border border-red-500/40 flex items-center justify-center mx-auto mb-3">
              <span className="text-red-400 text-lg">✕</span>
            </div>
            <p className="text-gray-200 font-medium">Connection error</p>
            <p className="text-red-400 text-sm mt-1">{error || 'Unable to reach server'}</p>
          </>
        )}
      </div>
    </div>
  );
};
