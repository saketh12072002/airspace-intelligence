'use client';

import React, { useState } from 'react';

export type MapTheme = 'dark' | 'voyager' | 'positron';

export const MAP_STYLES: Record<MapTheme, { name: string; url: string; icon: string }> = {
  dark: {
    name: 'Dark Night',
    url: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
    icon: '🌙',
  },
  voyager: {
    name: 'Vibrant World',
    url: 'https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json',
    icon: '🌍',
  },
  positron: {
    name: 'Light Day',
    url: 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json',
    icon: '☀️',
  },
};

interface MapStyleSelectorProps {
  currentTheme: MapTheme;
  onThemeChange: (theme: MapTheme) => void;
}

export const MapStyleSelector: React.FC<MapStyleSelectorProps> = ({
  currentTheme,
  onThemeChange,
}) => {
  const [open, setOpen] = useState(false);

  return (
    <div className="absolute top-16 right-3 z-30">
      <div className="relative">
        <button
          onClick={() => setOpen(!open)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-gray-900/90 hover:bg-gray-800 backdrop-blur-md border border-gray-700/80 rounded-lg shadow-xl text-xs font-semibold text-gray-200 transition-all hover:border-cyan-500/60"
          title="Change Map Style"
        >
          <span>{MAP_STYLES[currentTheme].icon}</span>
          <span>{MAP_STYLES[currentTheme].name}</span>
          <span className="text-[10px] text-gray-400">▼</span>
        </button>

        {open && (
          <div className="absolute right-0 mt-1.5 w-40 bg-gray-900/95 backdrop-blur-md border border-gray-700 rounded-xl shadow-2xl p-1.5 space-y-1 animate-in fade-in zoom-in-95 duration-150">
            {(Object.keys(MAP_STYLES) as MapTheme[]).map((key) => {
              const style = MAP_STYLES[key];
              const isSelected = currentTheme === key;
              return (
                <button
                  key={key}
                  onClick={() => {
                    onThemeChange(key);
                    setOpen(false);
                  }}
                  className={`w-full flex items-center gap-2 px-2.5 py-1.5 rounded-lg text-xs font-medium text-left transition-colors ${
                    isSelected
                      ? 'bg-cyan-600/30 text-cyan-300 border border-cyan-500/40'
                      : 'text-gray-300 hover:bg-gray-800 hover:text-white'
                  }`}
                >
                  <span className="text-sm">{style.icon}</span>
                  <span>{style.name}</span>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
