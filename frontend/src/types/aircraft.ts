/** Canonical aircraft state — mirrors the backend AircraftState schema. */
export interface Aircraft {
  icao24: string;
  callsign: string | null;
  origin_country: string;
  time_position: number | null;
  last_contact: number;
  longitude: number | null;
  latitude: number | null;
  baro_altitude: number | null;
  on_ground: boolean;
  velocity: number | null;
  true_track: number | null;
  vertical_rate: number | null;
  geo_altitude: number | null;
  squawk: string | null;
  position_source: number;
  category: number;
  ingested_at: string;
}

/** Wire format for /ws/aircraft messages. */
export interface AircraftUpdateMessage {
  type: 'aircraft_update';
  timestamp: string;
  added: Aircraft[];
  updated: Aircraft[];
  removed: string[];
}

export interface HeartbeatMessage {
  type: 'heartbeat';
  timestamp: string;
}

export type WSMessage = AircraftUpdateMessage | HeartbeatMessage;
export type WebSocketMessage = WSMessage;

export interface AircraftList {
  count: number;
  aircraft: Aircraft[];
}

/** Connection states for the WebSocket. */
export type ConnectionStatus = 'connecting' | 'connected' | 'disconnected' | 'error';

/** Health check response from /health. */
export interface HealthResponse {
  status: string;
  service: string;
  version: string;
}

/** GeoJSON feature for MapLibre rendering. */
export interface AircraftFeature {
  type: 'Feature';
  geometry: {
    type: 'Point';
    coordinates: [number, number]; // [lng, lat]
  };
  properties: {
    icao24: string;
    callsign: string;
    rotation: number;
    altitude: number;
    velocity: number;
    on_ground: boolean;
  };
}

export interface AircraftFeatureCollection {
  type: 'FeatureCollection';
  features: AircraftFeature[];
}

/** Airport information for departure / arrival. */
export interface AirportInfo {
  iata_code: string | null;
  icao_code: string | null;
  name: string | null;
  municipality: string | null;
  country_name: string | null;
  country_iso: string | null;
  latitude: number | null;
  longitude: number | null;
  elevation: number | null;
}

/** Airline / operator details. */
export interface AirlineInfo {
  name: string | null;
  icao: string | null;
  iata: string | null;
  callsign: string | null;
  country: string | null;
}

/** Static aircraft airframe specs and photo. */
export interface AircraftMetadata {
  type: string | null;
  icao_type: string | null;
  manufacturer: string | null;
  registration: string | null;
  registered_owner: string | null;
  registered_owner_country: string | null;
  url_photo: string | null;
  url_photo_thumbnail: string | null;
}

/** Enriched flight route from departure to destination. */
export interface FlightRoute {
  callsign: string;
  callsign_icao: string | null;
  callsign_iata: string | null;
  airline: AirlineInfo | null;
  origin: AirportInfo | null;
  destination: AirportInfo | null;
  total_distance_km: number | null;
  distance_flown_km: number | null;
  distance_remaining_km: number | null;
  progress_percent: number | null;
}

/** Full response from GET /api/aircraft/{icao24}/details. */
export interface FlightDetails {
  icao24: string;
  callsign: string | null;
  state: Aircraft | null;
  metadata: AircraftMetadata | null;
  route: FlightRoute | null;
}

