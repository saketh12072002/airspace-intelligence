"""Response generation and grounding engine for the Flight Search Agent."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple
from app.agent.planner import PlannedToolCall
from app.agent.state import AircraftReference, AirportReference, ConversationContext
from app.core.logging import get_logger

logger = get_logger(__name__)


def _extract_aircraft_reference(data: dict) -> Optional[AircraftReference]:
    """Convert an aircraft state dictionary to an AircraftReference for conversational memory."""
    if not isinstance(data, dict):
        return None

    # Handle wrapped structures (e.g. {'aircraft': {...}, 'distance_km': ...})
    target = data.get("aircraft", data)
    if not isinstance(target, dict) or "icao24" not in target:
        return None

    return AircraftReference(
        icao24=target.get("icao24", "").lower(),
        callsign=target.get("callsign"),
        origin_country=target.get("origin_country", "Unknown"),
        latitude=target.get("latitude"),
        longitude=target.get("longitude"),
        baro_altitude_m=target.get("baro_altitude_m"),
        altitude_ft=target.get("altitude_ft"),
        velocity_ms=target.get("velocity_ms"),
        speed_kmh=target.get("speed_kmh"),
        speed_knots=target.get("speed_knots"),
        true_track=target.get("true_track"),
        vertical_rate_ms=target.get("vertical_rate_ms"),
        on_ground=target.get("on_ground", False),
        flight_phase=data.get("flight_phase") or target.get("flight_phase"),
        last_contact=target.get("last_contact"),
    )


class FlightSearchResponseGenerator:
    """Transforms verified MCP tool results into structured, strictly-grounded responses."""

    def generate_response(
        self,
        user_query: str,
        plan: PlannedToolCall,
        tool_result: Any,
        context: ConversationContext,
    ) -> Tuple[str, Optional[AircraftReference], Optional[AirportReference]]:
        """Generate a grounded response and extract active entity references.

        Returns:
            (response_text, updated_aircraft_reference, updated_airport_reference)
        """
        tool_name = plan.tool_name
        data = tool_result if isinstance(tool_result, dict) else {}

        # ----------------------------------------------------------------------
        # Handle Tool 1: search_aircraft
        # ----------------------------------------------------------------------
        if tool_name == "search_aircraft":
            return self._handle_search_aircraft(plan, data)

        # ----------------------------------------------------------------------
        # Handle Tool 2: get_aircraft
        # ----------------------------------------------------------------------
        if tool_name == "get_aircraft":
            return self._handle_get_aircraft(plan, data, context)

        # ----------------------------------------------------------------------
        # Handle Tool 3: get_aircraft_history
        # ----------------------------------------------------------------------
        if tool_name == "get_aircraft_history":
            return self._handle_get_aircraft_history(plan, data)

        # ----------------------------------------------------------------------
        # Handle Tool 4: search_aircraft_in_area
        # ----------------------------------------------------------------------
        if tool_name == "search_aircraft_in_area":
            return self._handle_search_aircraft_in_area(plan, data)

        # ----------------------------------------------------------------------
        # Handle Tool 5: get_aircraft_near_airport
        # ----------------------------------------------------------------------
        if tool_name == "get_aircraft_near_airport":
            return self._handle_get_aircraft_near_airport(plan, data)

        # ----------------------------------------------------------------------
        # Handle Tool 6: get_airport
        # ----------------------------------------------------------------------
        if tool_name == "get_airport":
            return self._handle_get_airport(plan, data)

        # ----------------------------------------------------------------------
        # Handle Tool 7: get_airport_traffic
        # ----------------------------------------------------------------------
        if tool_name == "get_airport_traffic":
            return self._handle_get_airport_traffic(plan, data)

        # ----------------------------------------------------------------------
        # Handle Tool 8: get_flight_statistics
        # ----------------------------------------------------------------------
        if tool_name == "get_flight_statistics":
            return self._handle_get_flight_statistics(plan, data)

        return (
            f"Executed tool '{tool_name}' successfully:\n```json\n{data}\n```",
            None,
            None,
        )

    # --------------------------------------------------------------------------
    # Handlers for Individual Tools
    # --------------------------------------------------------------------------

    def _handle_search_aircraft(
        self,
        plan: PlannedToolCall,
        data: dict,
    ) -> Tuple[str, Optional[AircraftReference], Optional[AirportReference]]:
        total = data.get("total_matched", 0)
        aircraft_list = data.get("aircraft", [])

        target_callsign = plan.arguments.get("callsign")
        target_country = plan.arguments.get("country")

        if total == 0 or not aircraft_list:
            ident = target_callsign or target_country or "specified criteria"
            return (
                f"Aircraft matching '{ident}' is currently unavailable and not tracked within transponder coverage. "
                "The flight may not have departed yet, has already landed, or is outside transponder coverage.",
                None,
                None,
            )

        # If direct flight search matched single aircraft
        if len(aircraft_list) == 1 or target_callsign:
            ac = aircraft_list[0]
            ref = _extract_aircraft_reference(ac)
            callsign_str = ac.get("callsign") or ac.get("icao24")

            # Focused answer if user asked for specific attribute
            if plan.focus_attribute == "altitude":
                alt_ft = ac.get("altitude_ft")
                alt_m = ac.get("baro_altitude_m")
                if alt_ft is not None:
                    txt = (
                        f"**{callsign_str} Altitude**:\n"
                        f"- **Observed Live Data**: Altitude is **{alt_ft:,.0f} ft** ({alt_m:,.0f} m).\n"
                        f"- **Status**: {'On ground' if ac.get('on_ground') else 'Airborne'}.\n"
                        f"- **Transponder**: ICAO24 `{ac.get('icao24')}` ({ac.get('origin_country')})."
                    )
                else:
                    txt = f"Altitude data for {callsign_str} is currently unavailable in the live transponder broadcast."
                return txt, ref, None

            if plan.focus_attribute == "speed":
                spd_kts = ac.get("speed_knots")
                spd_kmh = ac.get("speed_kmh")
                if spd_kts is not None:
                    txt = (
                        f"**{callsign_str} Ground Speed**:\n"
                        f"- **Observed Live Data**: Speed is **{spd_kts:.0f} knots** ({spd_kmh:.0f} km/h).\n"
                        f"- **Transponder**: ICAO24 `{ac.get('icao24')}`."
                    )
                else:
                    txt = f"Ground speed data for {callsign_str} is currently unavailable."
                return txt, ref, None

            # General single flight report
            status = "On Ground" if ac.get("on_ground") else "Airborne"
            alt_str = f"{ac.get('altitude_ft', 0):,.0f} ft ({ac.get('baro_altitude_m', 0):,.0f} m)" if ac.get("altitude_ft") else "Unavailable"
            spd_str = f"{ac.get('speed_knots', 0):.0f} kts ({ac.get('speed_kmh', 0):.0f} km/h)" if ac.get("speed_knots") else "Unavailable"
            coords = f"lat {ac.get('latitude')}, lon {ac.get('longitude')}" if ac.get("latitude") is not None else "Unavailable"

            txt = (
                f"Flight **{callsign_str}** (ICAO `{ac.get('icao24')}`):\n\n"
                f"**Observed Live Data**:\n"
                f"- **Coordinates**: {coords}\n"
                f"- **Altitude**: {alt_str}\n"
                f"- **Ground Speed**: {spd_str}\n"
                f"- **Heading**: {ac.get('true_track', 'N/A')}°\n"
                f"- **Country of Registration**: {ac.get('origin_country')}\n\n"
                f"**Operational Status**:\n"
                f"- Aircraft is currently **{status}**."
            )
            return txt, ref, None

        # Multiple aircraft returned (e.g. Airline fleet or Country airspace search)
        lines = [f"Found **{total}** active aircraft matching your query:\n"]
        for i, a in enumerate(aircraft_list[:10], 1):
            c_sign = a.get("callsign") or a.get("icao24")
            alt = f"{a.get('altitude_ft', 0):,.0f} ft" if a.get("altitude_ft") else "N/A"
            spd = f"{a.get('speed_knots', 0):.0f} kts" if a.get("speed_knots") else "N/A"
            stat = "Ground" if a.get("on_ground") else "Airborne"
            lines.append(f"{i}. **{c_sign}** (`{a.get('icao24')}`) — {alt}, {spd}, {stat} ({a.get('origin_country')})")

        if total > 10:
            lines.append(f"\n*(Showing 10 of {total} aircraft)*")

        first_ref = _extract_aircraft_reference(aircraft_list[0]) if aircraft_list else None
        return "\n".join(lines), first_ref, None

    def _handle_get_aircraft(
        self,
        plan: PlannedToolCall,
        data: dict,
        context: ConversationContext,
    ) -> Tuple[str, Optional[AircraftReference], Optional[AirportReference]]:
        found = data.get("found", False)
        target_icao = plan.arguments.get("icao24", "")

        if not found or not data.get("aircraft"):
            msg = data.get("message") or f"Aircraft with ICAO24 '{target_icao}' is currently not tracked or out of coverage."
            return msg, None, None

        ac = data["aircraft"]
        ref = _extract_aircraft_reference(ac)
        callsign_str = ac.get("callsign") or ac.get("icao24")

        # Check for focused attribute (e.g. Follow-up "What's its altitude?")
        if plan.focus_attribute == "altitude":
            alt_ft = ac.get("altitude_ft")
            alt_m = ac.get("baro_altitude_m")
            if alt_ft is not None:
                txt = (
                    f"**{callsign_str} Altitude**:\n"
                    f"- **Observed Live Data**: Altitude is **{alt_ft:,.0f} ft** ({alt_m:,.0f} m).\n"
                    f"- **Status**: {'On ground' if ac.get('on_ground') else 'Airborne'}."
                )
            else:
                txt = f"Altitude data for {callsign_str} is currently unavailable."
            return txt, ref, None

        if plan.focus_attribute == "speed":
            spd_kts = ac.get("speed_knots")
            spd_kmh = ac.get("speed_kmh")
            if spd_kts is not None:
                txt = (
                    f"**{callsign_str} Speed**:\n"
                    f"- **Observed Live Data**: Ground speed is **{spd_kts:.0f} knots** ({spd_kmh:.0f} km/h)."
                )
            else:
                txt = f"Ground speed data for {callsign_str} is currently unavailable."
            return txt, ref, None

        if plan.focus_attribute == "heading":
            track = ac.get("true_track")
            txt = (
                f"**{callsign_str} Heading**:\n"
                f"- **Observed Live Data**: Heading is **{track}°**."
                if track is not None
                else f"Heading for {callsign_str} is currently unavailable."
            )
            return txt, ref, None

        if plan.focus_attribute == "position":
            lat, lon = ac.get("latitude"), ac.get("longitude")
            txt = (
                f"**{callsign_str} Position**:\n"
                f"- **Observed Live Data**: Latitude **{lat}**, Longitude **{lon}**."
                if lat is not None
                else f"Geographic position for {callsign_str} is currently unavailable."
            )
            return txt, ref, None

        status = "On Ground" if ac.get("on_ground") else "Airborne"
        alt_str = f"{ac.get('altitude_ft', 0):,.0f} ft ({ac.get('baro_altitude_m', 0):,.0f} m)" if ac.get("altitude_ft") else "Unavailable"
        spd_str = f"{ac.get('speed_knots', 0):.0f} kts ({ac.get('speed_kmh', 0):.0f} km/h)" if ac.get("speed_knots") else "Unavailable"
        coords = f"lat {ac.get('latitude')}, lon {ac.get('longitude')}" if ac.get("latitude") is not None else "Unavailable"

        txt = (
            f"Aircraft **{callsign_str}** (`{ac.get('icao24')}`):\n\n"
            f"**Observed Live Data**:\n"
            f"- **Coordinates**: {coords}\n"
            f"- **Altitude**: {alt_str}\n"
            f"- **Ground Speed**: {spd_str}\n"
            f"- **Heading**: {ac.get('true_track', 'N/A')}°\n"
            f"- **Vertical Rate**: {ac.get('vertical_rate_ms', '0.0')} m/s\n"
            f"- **Country**: {ac.get('origin_country')}\n\n"
            f"**Operational Status**: **{status}**"
        )
        return txt, ref, None

    def _handle_get_aircraft_history(
        self,
        plan: PlannedToolCall,
        data: dict,
    ) -> Tuple[str, Optional[AircraftReference], Optional[AirportReference]]:
        icao24 = data.get("icao24", plan.arguments.get("icao24", ""))
        count = data.get("record_count", 0)
        records = data.get("history", [])

        if count == 0 or not records:
            return (
                f"No historical telemetry points found for aircraft with ICAO24 '{icao24}'. "
                "History is recorded during active tracking sessions.",
                None,
                None,
            )

        first_pt = records[0]
        last_pt = records[-1]
        txt = (
            f"**Historical Telemetry Track for ICAO `{icao24}`**:\n\n"
            f"- **Historical Data**: {count} recorded trajectory points.\n"
            f"- **Earliest Recorded**: lat {first_pt.get('latitude')}, lon {first_pt.get('longitude')}, alt {first_pt.get('baro_altitude')}m\n"
            f"- **Latest Recorded**: lat {last_pt.get('latitude')}, lon {last_pt.get('longitude')}, alt {last_pt.get('baro_altitude')}m"
        )
        return txt, None, None

    def _handle_search_aircraft_in_area(
        self,
        plan: PlannedToolCall,
        data: dict,
    ) -> Tuple[str, Optional[AircraftReference], Optional[AirportReference]]:
        total = data.get("total_found", 0)
        radius = data.get("radius_km", plan.arguments.get("radius_km", 50.0))
        lat = data.get("center_latitude", plan.arguments.get("latitude"))
        lon = data.get("center_longitude", plan.arguments.get("longitude"))
        aircraft_list = data.get("aircraft", [])

        if total == 0 or not aircraft_list:
            return (
                f"No active aircraft currently detected within {radius:.0f} km of coordinates ({lat}, {lon}).",
                None,
                None,
            )

        lines = [
            f"Discovered **{total}** aircraft within **{radius:.0f} km** of coordinates ({lat}, {lon}):\n",
            "*(Sorted by proximity)*",
        ]

        for i, item in enumerate(aircraft_list[:10], 1):
            ac = item.get("aircraft", {})
            dist = item.get("distance_km", 0.0)
            c_sign = ac.get("callsign") or ac.get("icao24")
            alt = f"{ac.get('altitude_ft', 0):,.0f} ft" if ac.get("altitude_ft") else "N/A"
            stat = "Ground" if ac.get("on_ground") else "Airborne"
            lines.append(
                f"{i}. **{c_sign}** (`{ac.get('icao24')}`) — **{dist:.1f} km away** | {alt}, {stat} ({ac.get('origin_country')})"
            )

        if total > 10:
            lines.append(f"\n*(Showing closest 10 of {total} aircraft)*")

        first_ref = _extract_aircraft_reference(aircraft_list[0]) if aircraft_list else None
        return "\n".join(lines), first_ref, None

    def _handle_get_aircraft_near_airport(
        self,
        plan: PlannedToolCall,
        data: dict,
    ) -> Tuple[str, Optional[AircraftReference], Optional[AirportReference]]:
        found = data.get("found", False)
        code = plan.arguments.get("airport_code", "")

        if not found or not data.get("airport"):
            return f"Airport with code '{code}' was not found in the global database.", None, None

        apt = data["airport"]
        apt_ref = AirportReference(
            code=apt.get("icao_code", code),
            name=apt.get("name", "Airport"),
            municipality=apt.get("municipality", ""),
            country=apt.get("country_name", ""),
            latitude=apt.get("latitude", 0.0),
            longitude=apt.get("longitude", 0.0),
        )

        total = data.get("total_found", 0)
        radius = data.get("radius_km", 50.0)
        nearby = data.get("nearby_aircraft", [])

        apt_display = f"{apt['name']} ({apt.get('iata_code') or apt['icao_code']})"

        if total == 0 or not nearby:
            return (
                f"No active aircraft currently detected within {radius:.0f} km of **{apt_display}**.",
                None,
                apt_ref,
            )

        lines = [
            f"**{total}** aircraft operating within **{radius:.0f} km** of **{apt_display}**:\n"
        ]
        for i, item in enumerate(nearby[:10], 1):
            ac = item.get("aircraft", {})
            dist = item.get("distance_km", 0.0)
            c_sign = ac.get("callsign") or ac.get("icao24")
            alt = f"{ac.get('altitude_ft', 0):,.0f} ft" if ac.get("altitude_ft") else "N/A"
            stat = "On Ground" if ac.get("on_ground") else "Airborne"
            lines.append(
                f"{i}. **{c_sign}** (`{ac.get('icao24')}`) — **{dist:.1f} km from airfield** | {alt}, {stat}"
            )

        first_ref = _extract_aircraft_reference(nearby[0]) if nearby else None
        return "\n".join(lines), first_ref, apt_ref

    def _handle_get_airport(
        self,
        plan: PlannedToolCall,
        data: dict,
    ) -> Tuple[str, Optional[AircraftReference], Optional[AirportReference]]:
        found = data.get("found", False)
        code = plan.arguments.get("airport_code", "")

        if not found or not data.get("airport"):
            return f"Airport '{code}' not found in airport directory.", None, None

        apt = data["airport"]
        apt_ref = AirportReference(
            code=apt.get("icao_code", code),
            name=apt.get("name", "Airport"),
            municipality=apt.get("municipality", ""),
            country=apt.get("country_name", ""),
            latitude=apt.get("latitude", 0.0),
            longitude=apt.get("longitude", 0.0),
        )

        txt = (
            f"**{apt['name']}**:\n"
            f"- **ICAO / IATA**: `{apt.get('icao_code')}` / `{apt.get('iata_code') or 'N/A'}`\n"
            f"- **Location**: {apt.get('municipality')}, {apt.get('country_name')} ({apt.get('country_iso')})\n"
            f"- **Coordinates**: Latitude {apt.get('latitude')}, Longitude {apt.get('longitude')}\n"
            f"- **Elevation**: {apt.get('elevation_ft', 'N/A')} ft\n"
            f"- **Timezone**: {apt.get('timezone', 'N/A')}"
        )
        return txt, None, apt_ref

    def _handle_get_airport_traffic(
        self,
        plan: PlannedToolCall,
        data: dict,
    ) -> Tuple[str, Optional[AircraftReference], Optional[AirportReference]]:
        found = data.get("found", False)
        code = plan.arguments.get("airport_code", "")

        if not found or not data.get("airport"):
            return f"Airport '{code}' was not found.", None, None

        apt = data["airport"]
        apt_display = f"{apt['name']} ({apt.get('iata_code') or apt['icao_code']})"

        txt = (
            f"**Airspace Traffic Analysis for {apt_display}**:\n\n"
            f"**Derived Calculations (Flight Phase Heuristics)**:\n"
            f"- **Inbound (Approach)**: {data.get('inbound_count', 0)} flights descending towards runway\n"
            f"- **Outbound (Departure)**: {data.get('outbound_count', 0)} flights climbing after takeoff\n"
            f"- **Ground Operations**: {data.get('ground_count', 0)} aircraft confirmed on ground/taxiway\n"
            f"- **En-Route Overflights**: {data.get('en_route_count', 0)} flights transiting upper airspace\n"
            f"- **Total in Vicinity ({data.get('radius_km', 100):.0f} km)**: {data.get('total_aircraft', 0)}\n\n"
            f"**Operational Summary**:\n"
            f"{data.get('summary')}"
        )
        return txt, None, None

    def _handle_get_flight_statistics(
        self,
        plan: PlannedToolCall,
        data: dict,
    ) -> Tuple[str, Optional[AircraftReference], Optional[AirportReference]]:
        total = data.get("total_aircraft", 0)
        airborne = data.get("airborne_count", 0)
        ground = data.get("on_ground_count", 0)
        density = data.get("traffic_density", "MODERATE")
        alt = data.get("altitude_stats", {})
        spd = data.get("speed_stats", {})
        countries = data.get("top_origin_countries", [])

        top_c_str = ", ".join(f"{c.get('country')} ({c.get('count')})" for c in countries[:4])

        txt = (
            f"**Airspace Telemetry & Density Statistics**:\n\n"
            f"**Observed Live Fleet**:\n"
            f"- **Total Tracked Aircraft**: {total:,} ({airborne:,} airborne, {ground:,} on ground)\n"
            f"- **Airspace Traffic Density**: **{density}**\n\n"
            f"**Altitude Metrics**:\n"
            f"- Range: {alt.get('min_altitude_m', 0):,.0f} m to {alt.get('max_altitude_m', 0):,.0f} m\n"
            f"- Average Altitude: {alt.get('avg_altitude_m', 0):,.0f} m (Median: {alt.get('median_altitude_m', 0):,.0f} m)\n"
            f"- Cruise Altitude (FL260-FL390): {alt.get('cruise_altitude_count', 0)} aircraft\n\n"
            f"**Velocity Metrics**:\n"
            f"- Speed Range: {spd.get('min_speed_kmh', 0):.0f} to {spd.get('max_speed_kmh', 0):.0f} km/h\n"
            f"- Average Speed: {spd.get('avg_speed_kmh', 0):.0f} km/h\n\n"
            f"**Top Registration Countries**: {top_c_str}"
        )
        return txt, None, None
