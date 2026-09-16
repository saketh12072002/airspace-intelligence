"""Demonstration script executing all 8 Airspace Intelligence domain tools."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime

from app.domain.aircraft_service import AircraftService
from app.domain.airport_service import AirportService
from app.repositories.aircraft_repo import InMemoryAircraftRepository
from app.repositories.airport_repo import AirportRepository
from app.repositories.history_repo import HistoryRepository
from app.schemas.aircraft_state import AircraftState
from app.tools import create_default_registry


async def main():
    now_epoch = int(datetime.now(UTC).timestamp())

    # Curated realistic flights across key international airspaces
    sample_flights = [
        # Inbound to New Delhi (DEL / VIDP) - descending on approach
        AircraftState(
            icao24="800201",
            callsign="AIC101",
            origin_country="India",
            time_position=now_epoch,
            last_contact=now_epoch,
            longitude=77.18,
            latitude=28.52,
            baro_altitude=1100.0,
            on_ground=False,
            velocity=115.0,
            true_track=305.0,
            vertical_rate=-4.2,
            geo_altitude=1120.0,
            squawk="4211",
        ),
        # On ground at New Delhi (DEL / VIDP)
        AircraftState(
            icao24="800abc",
            callsign="SEJ512",
            origin_country="India",
            time_position=now_epoch,
            last_contact=now_epoch,
            longitude=77.10,
            latitude=28.56,
            baro_altitude=230.0,
            on_ground=True,
            velocity=12.0,
            true_track=90.0,
            vertical_rate=0.0,
            geo_altitude=230.0,
            squawk="1200",
        ),
        # En-route over northern India (high altitude cruise)
        AircraftState(
            icao24="80167f",
            callsign="IGO844",
            origin_country="India",
            time_position=now_epoch,
            last_contact=now_epoch,
            longitude=76.85,
            latitude=29.10,
            baro_altitude=10970.0,  # FL360
            on_ground=False,
            velocity=232.0,
            true_track=135.0,
            vertical_rate=0.0,
            geo_altitude=11100.0,
            squawk="2145",
        ),
        # Departing London Heathrow (LHR / EGLL) - climb out
        AircraftState(
            icao24="4006c0",
            callsign="BAW177",
            origin_country="United Kingdom",
            time_position=now_epoch,
            last_contact=now_epoch,
            longitude=-0.25,
            latitude=51.52,
            baro_altitude=2100.0,
            on_ground=False,
            velocity=155.0,
            true_track=275.0,
            vertical_rate=8.8,
            geo_altitude=2140.0,
            squawk="5201",
        ),
        # En-route cruise over Europe (Germany / Frankfurt)
        AircraftState(
            icao24="3c6444",
            callsign="DLH400",
            origin_country="Germany",
            time_position=now_epoch,
            last_contact=now_epoch,
            longitude=8.57,
            latitude=50.03,
            baro_altitude=11200.0,
            on_ground=False,
            velocity=245.0,
            true_track=95.0,
            vertical_rate=0.1,
            geo_altitude=11300.0,
            squawk="1000",
        ),
        # Inbound to New York JFK (JFK / KJFK)
        AircraftState(
            icao24="a12345",
            callsign="AAL100",
            origin_country="United States",
            time_position=now_epoch,
            last_contact=now_epoch,
            longitude=-73.72,
            latitude=40.61,
            baro_altitude=850.0,
            on_ground=False,
            velocity=98.0,
            true_track=315.0,
            vertical_rate=-3.8,
            geo_altitude=860.0,
            squawk="3401",
        ),
    ]

    # Initialize repository and domain layer
    aircraft_repo = InMemoryAircraftRepository()
    await aircraft_repo.upsert_many(sample_flights)

    airport_repo = AirportRepository()
    history_repo = HistoryRepository()
    await history_repo.record_positions(sample_flights)

    aircraft_svc = AircraftService(aircraft_repo, history_repo)
    airport_svc = AirportService(airport_repo, aircraft_repo)

    registry = create_default_registry(aircraft_svc, airport_svc)

    print("=" * 80)
    print("AIRSPACE INTELLIGENCE — DOMAIN TOOL LAYER EXECUTION REPORT")
    print("=" * 80)

    # 1. search_aircraft
    print("\n[Tool 1: search_aircraft] -> Search by country='India'")
    t1_res = await registry.execute("search_aircraft", {"country": "India"})
    print(f"Matched: {t1_res.total_matched} aircraft")
    for a in t1_res.aircraft:
        print(f"  - {a.icao24} | Callsign: {a.callsign} | Alt: {a.altitude_ft} ft | Speed: {a.speed_kmh} km/h")

    # 2. get_aircraft
    print("\n[Tool 2: get_aircraft] -> ICAO24='800201'")
    t2_res = await registry.execute("get_aircraft", {"icao24": "800201"})
    print(f"Found: {t2_res.found} | Callsign: {t2_res.aircraft.callsign} | Reg Country: {t2_res.aircraft.origin_country}")

    # 3. get_aircraft_history
    print("\n[Tool 3: get_aircraft_history] -> ICAO24='800201'")
    t3_res = await registry.execute("get_aircraft_history", {"icao24": "800201"})
    print(f"Points recorded: {t3_res.record_count}")
    for p in t3_res.history:
        print(f"  - Position: lat={p.latitude}, lon={p.longitude} | Alt: {p.baro_altitude}m")

    # 4. search_aircraft_in_area
    print("\n[Tool 4: search_aircraft_in_area] -> Near Delhi coordinates (lat 28.5665, lon 77.1031, r=100km)")
    t4_res = await registry.execute("search_aircraft_in_area", {
        "latitude": 28.5665,
        "longitude": 77.1031,
        "radius_km": 100.0,
    })
    print(f"Found {t4_res.total_found} aircraft within {t4_res.radius_km}km:")
    for item in t4_res.aircraft:
        print(f"  - {item.aircraft.callsign} ({item.aircraft.icao24}) -> Distance: {item.distance_km:.2f} km")

    # 5. get_airport
    print("\n[Tool 5: get_airport] -> Code='VIDP'")
    t5_res = await registry.execute("get_airport", {"airport_code": "VIDP"})
    print(f"Airport: {t5_res.airport.name} ({t5_res.airport.iata_code}/{t5_res.airport.icao_code}) | {t5_res.airport.municipality}, {t5_res.airport.country_name}")

    # 6. get_aircraft_near_airport
    print("\n[Tool 6: get_aircraft_near_airport] -> Airport='DEL', radius=80km")
    t6_res = await registry.execute("get_aircraft_near_airport", {"airport_code": "DEL", "radius_km": 80.0})
    print(f"Nearby at {t6_res.airport.name}: {t6_res.total_found} aircraft")
    for item in t6_res.nearby_aircraft:
        print(f"  - {item.aircraft.callsign} | Distance: {item.distance_km:.2f} km | Ground: {item.aircraft.on_ground}")

    # 7. get_airport_traffic
    print("\n[Tool 7: get_airport_traffic] -> Airport='DEL', radius=100km")
    t7_res = await registry.execute("get_airport_traffic", {"airport_code": "DEL", "radius_km": 100.0})
    print(f"Operational breakdown: Inbound={t7_res.inbound_count}, Outbound={t7_res.outbound_count}, Ground={t7_res.ground_count}, En-route={t7_res.en_route_count}")
    print(f"Summary: {t7_res.summary}")

    # 8. get_flight_statistics
    print("\n[Tool 8: get_flight_statistics] -> Global fleet statistics")
    t8_res = await registry.execute("get_flight_statistics", {})
    print(f"Total: {t8_res.total_aircraft} (Airborne: {t8_res.airborne_count}, Ground: {t8_res.on_ground_count})")
    print(f"Traffic density: {t8_res.traffic_density}")
    print(f"Altitudes: Min={t8_res.altitude_stats.min_altitude_m}m, Max={t8_res.altitude_stats.max_altitude_m}m, Avg={t8_res.altitude_stats.avg_altitude_m:.1f}m")
    print(f"Speeds: Min={t8_res.speed_stats.min_speed_kmh} km/h, Max={t8_res.speed_stats.max_speed_kmh} km/h, Avg={t8_res.speed_stats.avg_speed_kmh:.1f} km/h")
    print(f"Top Origin Countries: {[(c.country, c.count) for c in t8_res.top_origin_countries]}")

    # MCP Manifest demonstration
    print("\n" + "=" * 80)
    print("MODEL CONTEXT PROTOCOL (MCP) TOOL MANIFEST")
    print("=" * 80)
    manifest = registry.get_mcp_manifest()
    print(f"Total exported tools: {len(manifest)}")
    for tool_def in manifest:
        props = list(tool_def["inputSchema"].get("properties", {}).keys())
        print(f"  • {tool_def['name']}: {tool_def['description'][:60]}... (args: {props})")

    print("\n[✓] All 8 domain tools executed successfully with validated Pydantic input/output schemas!")


if __name__ == "__main__":
    asyncio.run(main())
