"""Interactive showcase of the Airspace Intelligence Flight Search Agent."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from app.agent import FlightSearchAgent, FlightSearchMCPClient
from app.domain.aircraft_service import AircraftService
from app.domain.airport_service import AirportService
from app.mcp.adapter import create_mcp_server
from app.repositories.aircraft_repo import InMemoryAircraftRepository
from app.repositories.airport_repo import AirportRepository
from app.repositories.history_repo import HistoryRepository
from app.schemas.aircraft_state import AircraftState
from app.tools.registry import create_default_registry


async def main():
    now_epoch = int(datetime.now(UTC).timestamp())

    # Build realistic flight fleet
    fleet = [
        # Flight AI203 (AIC203) descending on approach to Delhi (VIDP)
        AircraftState(
            icao24="80167f",
            callsign="AIC203",
            origin_country="India",
            time_position=now_epoch,
            last_contact=now_epoch,
            longitude=77.12,
            latitude=28.54,
            baro_altitude=3200.0,
            on_ground=False,
            velocity=180.0,
            true_track=310.0,
            vertical_rate=-4.0,
            geo_altitude=3250.0,
            squawk="4211",
        ),
        # Flight AI101 (AIC101) on ground at Mumbai (BOM)
        AircraftState(
            icao24="800201",
            callsign="AIC101",
            origin_country="India",
            time_position=now_epoch,
            last_contact=now_epoch,
            longitude=72.88,
            latitude=19.10,
            baro_altitude=39.0,
            on_ground=True,
            velocity=15.0,
            true_track=90.0,
            vertical_rate=0.0,
            geo_altitude=39.0,
            squawk="1200",
        ),
        # SpiceJet SEJ512 airborne near Mumbai within 100km
        AircraftState(
            icao24="800abc",
            callsign="SEJ512",
            origin_country="India",
            time_position=now_epoch,
            last_contact=now_epoch,
            longitude=72.85,
            latitude=19.15,
            baro_altitude=1500.0,
            on_ground=False,
            velocity=110.0,
            true_track=210.0,
            vertical_rate=5.0,
            geo_altitude=1520.0,
            squawk="3144",
        ),
        # Lufthansa DLH400 cruising over Germany
        AircraftState(
            icao24="3c6444",
            callsign="DLH400",
            origin_country="Germany",
            time_position=now_epoch,
            last_contact=now_epoch,
            longitude=8.57,
            latitude=50.03,
            baro_altitude=10500.0,
            on_ground=False,
            velocity=240.0,
            true_track=95.0,
            vertical_rate=0.0,
            geo_altitude=10600.0,
            squawk="1000",
        ),
    ]

    # Initialize repository and domain layer
    aircraft_repo = InMemoryAircraftRepository()
    await aircraft_repo.upsert_many(fleet)
    airport_repo = AirportRepository()
    history_repo = HistoryRepository()
    await history_repo.record_positions(fleet)

    aircraft_svc = AircraftService(aircraft_repo, history_repo)
    airport_svc = AirportService(airport_repo, aircraft_repo)

    registry = create_default_registry(aircraft_svc, airport_svc)
    mcp_server = create_mcp_server(registry, server_name="demo-copilot-mcp")
    mcp_client = FlightSearchMCPClient(mcp_server=mcp_server)

    agent = FlightSearchAgent(mcp_client=mcp_client)

    print("=" * 80)
    print("AIRSPACE INTELLIGENCE — FLIGHT SEARCH AGENT INTERACTIVE DEMO")
    print("=" * 80)

    # 1. Geographic search near Delhi
    print("\n[Query 1] Which aircraft are near Delhi?")
    res1 = await agent.ask("Which aircraft are near Delhi?")
    print(f"Tool executed: {res1.tool_called} (args: {res1.tool_arguments})")
    print(res1.text)

    # 2. Direct lookup of AI203
    session_id = "copilot-session-1"
    print("\n" + "-" * 80)
    print("[Query 2] Where is AI203?")
    res2 = await agent.ask("Where is AI203?", conversation_id=session_id)
    print(f"Tool executed: {res2.tool_called} (args: {res2.tool_arguments})")
    print(res2.text)

    # 3. Follow-up 1 (Pronoun: "its")
    print("\n" + "-" * 80)
    print("[Query 3 - Follow-up 1] What's its altitude?")
    res3 = await agent.ask("What's its altitude?", conversation_id=session_id)
    print(f"Tool executed: {res3.tool_called} (args: {res3.tool_arguments})")
    print(res3.text)

    # 4. Follow-up 2 (Pronoun: "it")
    print("\n" + "-" * 80)
    print("[Query 4 - Follow-up 2] How fast is it going?")
    res4 = await agent.ask("How fast is it going?", conversation_id=session_id)
    print(f"Tool executed: {res4.tool_called} (args: {res4.tool_arguments})")
    print(res4.text)

    # 5. Airline fleet search
    print("\n" + "-" * 80)
    print("[Query 5] Which Air India aircraft are currently airborne?")
    res5 = await agent.ask("Which Air India aircraft are currently airborne?")
    print(f"Tool executed: {res5.tool_called} (args: {res5.tool_arguments})")
    print(res5.text)

    # 6. Radial distance from Mumbai
    print("\n" + "-" * 80)
    print("[Query 6] What aircraft are within 100 km of Mumbai?")
    res6 = await agent.ask("What aircraft are within 100 km of Mumbai?")
    print(f"Tool executed: {res6.tool_called} (args: {res6.tool_arguments})")
    print(res6.text)

    # 7. Airport vicinity
    print("\n" + "-" * 80)
    print("[Query 7] Which aircraft are near Delhi airport?")
    res7 = await agent.ask("Which aircraft are near Delhi airport?")
    print(f"Tool executed: {res7.tool_called} (args: {res7.tool_arguments})")
    print(res7.text)

    # 8. Country airspace search
    print("\n" + "-" * 80)
    print("[Query 8] Show aircraft currently flying over India.")
    res8 = await agent.ask("Show aircraft currently flying over India.")
    print(f"Tool executed: {res8.tool_called} (args: {res8.tool_arguments})")
    print(res8.text)

    # 9. Missing aircraft test (Zero hallucination)
    print("\n" + "-" * 80)
    print("[Query 9 - Missing Flight] Where is flight AI9999?")
    res9 = await agent.ask("Where is flight AI9999?")
    print(f"Tool executed: {res9.tool_called} (args: {res9.tool_arguments})")
    print(res9.text)

    print("\n" + "=" * 80)
    print("[✓] Flight Search Agent demonstration complete!")
    print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
