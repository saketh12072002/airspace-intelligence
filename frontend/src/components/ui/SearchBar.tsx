'use client';

import React, { useState, useCallback } from 'react';

interface SearchBarProps {
  onSearch: (query: string) => void;
}

export const SearchBar: React.FC<SearchBarProps> = ({ onSearch }) => {
  const [query, setQuery] = useState('');

  const handleSubmit = useCallback(
    (e: React.FormEvent) => {
      e.preventDefault();
      onSearch(query.trim().toUpperCase());
    },
    [query, onSearch],
  );

  const handleClear = useCallback(() => {
    setQuery('');
    onSearch('');
  }, [onSearch]);

  return (
    <form
      onSubmit={handleSubmit}
      className="absolute top-14 left-3 z-40 flex items-center bg-gray-900/90 backdrop-blur-sm rounded-lg border border-gray-700 shadow-lg overflow-hidden"
    >
      <svg
        className="w-4 h-4 text-gray-500 ml-3 shrink-0"
        fill="none"
        stroke="currentColor"
        viewBox="0 0 24 24"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
        />
      </svg>
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search callsign or ICAO…"
        className="bg-transparent text-sm text-gray-200 placeholder-gray-500 px-2 py-2 w-48 outline-none"
      />
      {query && (
        <button
          type="button"
          onClick={handleClear}
          className="text-gray-500 hover:text-gray-300 pr-3 text-xs"
        >
          ✕
        </button>
      )}
    </form>
  );
};
