"""Semantic intent planner and tool selection engine for the Flight Search Agent."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field

from app.agent.state import ConversationContext
from app.core.logging import get_logger

logger = get_logger(__name__)

# Key global metropolitan reference coordinates
CITY_COORDINATES: Dict[str, Tuple[float, float, str]] = {
    # City name -> (latitude, longitude, primary airport code)
    "delhi": (28.5665, 77.1031, "VIDP"),
    "new delhi": (28.5665, 77.1031, "VIDP"),
    "mumbai": (19.0896, 72.8656, "VABB"),
    "bombay": (19.0896, 72.8656, "VABB"),
    "bengaluru": (13.1986, 77.7066, "VOBL"),
    "bangalore": (13.1986, 77.7066, "VOBL"),
    "chennai": (12.9941, 80.1709, "VOMM"),
    "madras": (12.9941, 80.1709, "VOMM"),
    "hyderabad": (17.2403, 78.4294, "VOHS"),
    "kolkata": (22.6547, 88.4467, "VECC"),
    "calcutta": (22.6547, 88.4467, "VECC"),
    "london": (51.4700, -0.4543, "EGLL"),
    "new york": (40.6413, -73.7781, "KJFK"),
    "nyc": (40.6413, -73.7781, "KJFK"),
    "frankfurt": (50.0379, 8.5622, "EDDF"),
    "paris": (49.0097, 2.5479, "LFPG"),
    "dubai": (25.2532, 55.3657, "OMDB"),
    "singapore": (1.3644, 103.9915, "WSSS"),
    "tokyo": (35.7720, 140.3929, "RJAA"),
}

# Airline designator mappings
AIRLINE_LOOKUP: Dict[str, Tuple[str, str]] = {
    # normalized phrase -> (ICAO prefix, Country)
    "air india": ("AIC", "India"),
    "indigo": ("IGO", "India"),
    "spicejet": ("SEJ", "India"),
    "vistara": ("VTI", "India"),
    "air india express": ("AXB", "India"),
    "akasa": ("AKJ", "India"),
    "akasa air": ("AKJ", "India"),
    "lufthansa": ("DLH", "Germany"),
    "british airways": ("BAW", "United Kingdom"),
    "emirates": ("UAE", "United Arab Emirates"),
    "etihad": ("ETD", "United Arab Emirates"),
    "qatar": ("QTR", "Qatar"),
    "qatar airways": ("QTR", "Qatar"),
    "air france": ("AFR", "France"),
    "klm": ("KLM", "Netherlands"),
    "united": ("UAL", "United States"),
    "united airlines": ("UAL", "United States"),
    "american": ("AAL", "United States"),
    "american airlines": ("AAL", "United States"),
    "delta": ("DAL", "United States"),
    "delta air lines": ("DAL", "United States"),
    "singapore airlines": ("SIA", "Singapore"),
}


class PlannedToolCall(BaseModel):
    """A tool call selected by the planner with validated parameters."""

    tool_name: str
    arguments: Dict[str, Any]
    rationale: str
    query_intent: str = Field(
        description="Identified user intent: DIRECT_AIRCRAFT, AREA_SEARCH, AIRPORT_TRAFFIC, AIRLINE_FLEET, FOLLOW_UP, STATISTICS"
    )
    focus_attribute: Optional[str] = Field(
        default=None,
        description="Specific telemetry attribute requested (altitude, speed, heading, position, etc.)",
    )


def extract_radius_km(text: str, default: float = 50.0) -> float:
    """Extract numeric search radius in km from query string."""
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:km|kilometres|kilometers|k\.m\.)", text, re.IGNORECASE)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return default


def extract_flight_or_icao(text: str) -> Optional[Tuple[str, str]]:
    """Extract flight callsign or ICAO24 hex address from query.

    Returns:
        (type, value) where type is 'callsign' or 'icao24', or None.
    """
    clean = text.strip()

    # Match explicit ICAO hex codes (e.g. "80167f", "3c6444", "a12345")
    m_hex = re.search(r"\b([0-9a-fA-F]{6})\b", clean)
    if m_hex and not re.search(r"[g-zG-Z]", m_hex.group(1)):
        # If it's pure hex and doesn't match standard callsign prefixes like AIC/BAW
        val = m_hex.group(1).lower()
        # Avoid treating common words as hex if not preceded by aircraft/icao
        if re.search(r"(?:icao|aircraft|hex|transponder|plane)\s*([0-9a-fA-F]{6})", clean, re.IGNORECASE):
            return ("icao24", val)
        if re.search(r"^[0-9a-fA-F]{6}$", clean):
            return ("icao24", val)

    # Known commercial IATA airline codes
    iata_to_icao = {
        "AI": "AIC",
        "6E": "IGO",
        "SG": "SEJ",
        "UK": "VTI",
        "IX": "AXB",
        "QP": "AKJ",
        "LH": "DLH",
        "BA": "BAW",
        "EK": "UAE",
        "EY": "ETD",
        "QR": "QTR",
        "AF": "AFR",
        "KL": "KLM",
        "UA": "UAL",
        "AA": "AAL",
        "DL": "DAL",
        "SQ": "SIA",
    }

    # Match IATA flight number with known 2-letter airline code (e.g. "AI203", "AI 203", "6E204", "LH400")
    m_iata = re.search(r"\b([a-zA-Z0-9]{2})\s*(\d{1,4}[a-zA-Z]?)\b", clean)
    if m_iata:
        code, num = m_iata.group(1).upper(), m_iata.group(2).upper()
        if code in iata_to_icao:
            return ("callsign", f"{iata_to_icao[code]}{num}")
        # Only match arbitrary 2-char code if explicitly preceded by flight keyword
        if re.search(r"(?:flight|flight\s*no|flt)\s*" + re.escape(m_iata.group(0)), clean, re.IGNORECASE):
            return ("callsign", f"{code}{num}")

    # Match standard ICAO callsigns (3 letters + 1-4 digits/letters, e.g. "AIC101", "DLH400")
    m_icao = re.search(r"\b([A-Z]{3}\d{1,4}[A-Z]?)\b", clean, re.IGNORECASE)
    if m_icao:
        return ("callsign", m_icao.group(1).upper())

    return None


class FlightSearchPlanner:
    """Deterministic intent parser and tool selection engine for aviation information retrieval."""

    def plan(
        self,
        user_query: str,
        context: ConversationContext,
    ) -> PlannedToolCall:
        """Analyze user query and context to select the optimal MCP tool and parameters."""
        q = user_query.strip()
        q_lower = q.lower()

        # ----------------------------------------------------------------------
        # 1. Follow-up pronoun resolution ("What's its altitude?", "How fast is it going?")
        # ----------------------------------------------------------------------
        active_aircraft = context.get_last_aircraft()
        is_follow_up = bool(
            re.search(
                r"\b(it|its|that|this flight|that flight|the plane|the aircraft|its speed|its altitude|its heading)\b",
                q_lower,
            )
            or (
                active_aircraft is not None
                and any(
                    kw in q_lower
                    for kw in [
                        "how fast",
                        "what altitude",
                        "what's its altitude",
                        "where is it",
                        "is it on ground",
                        "is it airborne",
                        "what is its altitude",
                    ]
                )
            )
        )

        if is_follow_up and active_aircraft:
            focus = None
            if "alt" in q_lower or "height" in q_lower:
                focus = "altitude"
            elif "fast" in q_lower or "speed" in q_lower or "velocity" in q_lower:
                focus = "speed"
            elif "heading" in q_lower or "direction" in q_lower or "track" in q_lower:
                focus = "heading"
            elif "ground" in q_lower or "landed" in q_lower or "airborne" in q_lower:
                focus = "status"
            elif "where" in q_lower or "location" in q_lower or "coord" in q_lower:
                focus = "position"

            # Query fresh state for the active aircraft
            return PlannedToolCall(
                tool_name="get_aircraft",
                arguments={"icao24": active_aircraft.icao24},
                rationale=f"Follow-up regarding previously referenced aircraft {active_aircraft.callsign or active_aircraft.icao24}.",
                query_intent="FOLLOW_UP",
                focus_attribute=focus,
            )

        # ----------------------------------------------------------------------
        # 2. Direct Aircraft / Flight lookup ("Where is AI203?", "Find 80167f", "What is altitude of aircraft X?")
        # ----------------------------------------------------------------------
        extracted = extract_flight_or_icao(q)
        if extracted:
            kind, val = extracted
            focus = None
            if "alt" in q_lower:
                focus = "altitude"
            elif "speed" in q_lower or "fast" in q_lower:
                focus = "speed"

            if kind == "icao24":
                return PlannedToolCall(
                    tool_name="get_aircraft",
                    arguments={"icao24": val},
                    rationale=f"Direct lookup of single aircraft by 24-bit ICAO transponder address '{val}'.",
                    query_intent="DIRECT_AIRCRAFT",
                    focus_attribute=focus,
                )
            else:
                return PlannedToolCall(
                    tool_name="search_aircraft",
                    arguments={"callsign": val, "limit": 10},
                    rationale=f"Search for flight with callsign '{val}'.",
                    query_intent="DIRECT_AIRCRAFT",
                    focus_attribute=focus,
                )

        # ----------------------------------------------------------------------
        # 3. Airport Vicinity & Traffic ("Which aircraft are near Delhi airport?", "DEL airport traffic")
        # ----------------------------------------------------------------------
        if "airport" in q_lower or "runway" in q_lower or "arrivals" in q_lower or "departures" in q_lower:
            # Check for city or airport code mentioned
            for city, (lat, lon, apt_code) in CITY_COORDINATES.items():
                if city in q_lower:
                    radius = extract_radius_km(q_lower, default=50.0)
                    if "traffic" in q_lower or "arrivals" in q_lower or "departures" in q_lower:
                        return PlannedToolCall(
                            tool_name="get_airport_traffic",
                            arguments={"airport_code": apt_code, "radius_km": radius},
                            rationale=f"Analyze airport operational traffic breakdown for {city.title()} Airport ({apt_code}).",
                            query_intent="AIRPORT_TRAFFIC",
                        )
                    return PlannedToolCall(
                        tool_name="get_aircraft_near_airport",
                        arguments={"airport_code": apt_code, "radius_km": radius},
                        rationale=f"Find active aircraft operating near {city.title()} Airport ({apt_code}).",
                        query_intent="AIRPORT_TRAFFIC",
                    )

            # Check 3/4 letter code (e.g. "near VIDP", "near DEL")
            m_code = re.search(r"\b([A-Z]{3,4})\b", q)
            if m_code:
                code = m_code.group(1)
                radius = extract_radius_km(q_lower, default=50.0)
                return PlannedToolCall(
                    tool_name="get_aircraft_near_airport",
                    arguments={"airport_code": code, "radius_km": radius},
                    rationale=f"Find active aircraft near airport '{code}'.",
                    query_intent="AIRPORT_TRAFFIC",
                )

        # ----------------------------------------------------------------------
        # 4. City / Geographic Area Proximity ("Which aircraft are near Delhi?", "within 100 km of Mumbai")
        # ----------------------------------------------------------------------
        for city, (lat, lon, apt_code) in CITY_COORDINATES.items():
            if city in q_lower:
                radius = extract_radius_km(q_lower, default=100.0)
                return PlannedToolCall(
                    tool_name="search_aircraft_in_area",
                    arguments={
                        "latitude": lat,
                        "longitude": lon,
                        "radius_km": radius,
                        "limit": 50,
                    },
                    rationale=f"Radial geographic search within {radius:.0f}km of {city.title()} coordinates ({lat}, {lon}).",
                    query_intent="AREA_SEARCH",
                )

        # ----------------------------------------------------------------------
        # 5. Airline Fleet Inquiries ("Which Air India aircraft are currently airborne?")
        # ----------------------------------------------------------------------
        for name, (prefix, country) in AIRLINE_LOOKUP.items():
            if name in q_lower:
                return PlannedToolCall(
                    tool_name="search_aircraft",
                    arguments={"callsign": prefix, "country": country, "limit": 50},
                    rationale=f"Filter active aircraft for airline '{name.title()}' (prefix {prefix}).",
                    query_intent="AIRLINE_FLEET",
                )

        # ----------------------------------------------------------------------
        # 6. Regional / Country Airspace Inquiries ("Show aircraft currently flying over India")
        # ----------------------------------------------------------------------
        country_matches = [
            ("india", "India"),
            ("germany", "Germany"),
            ("united states", "United States"),
            ("united kingdom", "United Kingdom"),
            ("france", "France"),
            ("japan", "Japan"),
            ("australia", "Australia"),
            ("uae", "United Arab Emirates"),
            ("emirates", "United Arab Emirates"),
        ]
        for term, country_name in country_matches:
            if term in q_lower:
                return PlannedToolCall(
                    tool_name="search_aircraft",
                    arguments={"country": country_name, "limit": 50},
                    rationale=f"Search for active flights registered or operating under country '{country_name}'.",
                    query_intent="AREA_SEARCH",
                )

        # ----------------------------------------------------------------------
        # 7. Airspace Statistics / Density
        # ----------------------------------------------------------------------
        if "stat" in q_lower or "density" in q_lower or "how many aircraft" in q_lower or "busy" in q_lower:
            return PlannedToolCall(
                tool_name="get_flight_statistics",
                arguments={},
                rationale="Compute fleet-wide telemetry statistics and traffic density.",
                query_intent="STATISTICS",
            )

        # ----------------------------------------------------------------------
        # 8. Fallback General Fleet Search
        # ----------------------------------------------------------------------
        return PlannedToolCall(
            tool_name="search_aircraft",
            arguments={"limit": 20},
            rationale="General active aircraft discovery.",
            query_intent="GENERAL_SEARCH",
        )
