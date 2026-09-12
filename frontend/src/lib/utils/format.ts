/** Display-formatting helpers used across the UI. */

/** Format altitude in feet (input is metres). */
export function formatAltitude(metres: number | null): string {
  if (metres === null || metres === undefined) return '—';
  const feet = metres * 3.28084;
  return `${Math.round(feet).toLocaleString()} ft`;
}

/** Format speed in knots (input is m/s). */
export function formatSpeed(ms: number | null): string {
  if (ms === null || ms === undefined) return '—';
  const knots = ms * 1.94384;
  return `${Math.round(knots)} kts`;
}

/** Format vertical rate in ft/min (input is m/s). */
export function formatVerticalRate(ms: number | null): string {
  if (ms === null || ms === undefined) return '—';
  const fpm = ms * 196.85;
  const sign = fpm > 0 ? '+' : '';
  return `${sign}${Math.round(fpm)} ft/min`;
}

/** Format heading / true track in degrees. */
export function formatHeading(degrees: number | null): string {
  if (degrees === null || degrees === undefined) return '—';
  return `${Math.round(degrees)}°`;
}

/** Format coordinates. */
export function formatCoord(value: number | null, decimals = 4): string {
  if (value === null || value === undefined) return '—';
  return value.toFixed(decimals);
}

/** Format a unix timestamp as a locale time string. */
export function formatTimestamp(unix: number | null): string {
  if (unix === null || unix === undefined) return '—';
  return new Date(unix * 1000).toLocaleTimeString();
}

/** Format an ISO timestamp as locale time. */
export function formatISOTime(iso: string | null): string {
  if (!iso) return '—';
  return new Date(iso).toLocaleTimeString();
}

/** Clean up callsign display. */
export function formatCallsign(callsign: string | null): string {
  if (!callsign || callsign.trim() === '') return '—';
  return callsign.trim();
}
