"""OpenSky Network REST API client.

Implements :class:`app.services.base.ADSBProvider` using ``httpx`` and the
public OpenSky ``/states/all`` endpoint.

Reference: https://openskynetwork.github.io/opensky-api/rest.html
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.schemas.aircraft_state import AircraftState
from app.services.base import ADSBProvider
from app.services.opensky.models import OpenSkyStatesResponse

logger = get_logger(__name__)


class OpenSkyAPIError(Exception):
    """Raised when the OpenSky API returns an unrecoverable error."""

    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"OpenSky API error {status_code}: {detail}")


class OpenSkyRateLimitError(OpenSkyAPIError):
    """Raised on HTTP 429 — caller should back off."""

    def __init__(self, retry_after: Optional[int] = None) -> None:
        self.retry_after = retry_after
        super().__init__(429, f"Rate limited (retry after {retry_after}s)")


class OpenSkyAuthError(OpenSkyAPIError):
    """Raised on HTTP 401 — credentials are invalid."""

    def __init__(self) -> None:
        super().__init__(401, "Authentication failed — check OPENSKY_USERNAME / OPENSKY_PASSWORD")


class OpenSkyClient(ADSBProvider):
    """Fetches live ADS-B state vectors from the OpenSky Network REST API.

    Usage::

        client = OpenSkyClient(settings)
        await client.connect()
        states = await client.fetch_states(bounds=(45.0, 5.0, 48.0, 10.0))
        await client.disconnect()
    """

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._base_url = settings.opensky_base_url.rstrip("/")
        self._client: Optional[httpx.AsyncClient] = None

    async def connect(self) -> None:
        """Create the underlying ``httpx.AsyncClient``."""
        auth: Optional[tuple[str, str]] = None
        if self.settings.opensky_username and self.settings.opensky_password:
            auth = (self.settings.opensky_username, self.settings.opensky_password)
            logger.info("OpenSkyClient: using authenticated mode")
        else:
            logger.info("OpenSkyClient: using anonymous mode (stricter rate limits)")

        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            auth=auth,
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
            headers={"Accept": "application/json"},
        )

    async def disconnect(self) -> None:
        """Gracefully close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
            logger.info("OpenSkyClient disconnected")

    # ------------------------------------------------------------------
    # ADSBProvider interface
    # ------------------------------------------------------------------

    async def fetch_states(
        self,
        bounds: Optional[Tuple[float, float, float, float]] = None,
    ) -> List[Dict[str, Any]]:
        """Fetch raw state dicts from OpenSky (satisfies base-class contract).

        Returns a list of dicts that can each be passed to
        ``AircraftState(**d)``.  Most callers should prefer
        :meth:`fetch_aircraft_states` which returns typed objects directly.
        """
        aircraft_states = await self.fetch_aircraft_states(bounds)
        return [s.model_dump() for s in aircraft_states]

    # ------------------------------------------------------------------
    # Typed public API
    # ------------------------------------------------------------------

    async def fetch_aircraft_states(
        self,
        bounds: Optional[Tuple[float, float, float, float]] = None,
    ) -> List[AircraftState]:
        """Query ``/states/all`` and return normalised :class:`AircraftState` objects.

        Args:
            bounds: Optional ``(lamin, lomin, lamax, lomax)`` bounding box.

        Returns:
            List of normalised aircraft states.

        Raises:
            OpenSkyAuthError: on 401
            OpenSkyRateLimitError: on 429
            OpenSkyAPIError: on other HTTP errors
            httpx.TimeoutException: on request timeout
        """
        if self._client is None:
            raise RuntimeError("OpenSkyClient is not connected — call connect() first")

        params: Dict[str, Any] = {}
        if bounds is not None:
            lamin, lomin, lamax, lomax = bounds
            params.update(lamin=lamin, lomin=lomin, lamax=lamax, lomax=lomax)

        t0 = time.monotonic()
        try:
            response = await self._client.get("/states/all", params=params or None)
        except httpx.TimeoutException:
            logger.error("OpenSky API request timed out")
            raise

        elapsed_ms = (time.monotonic() - t0) * 1000
        logger.debug("OpenSky /states/all responded in %.0f ms (HTTP %d)", elapsed_ms, response.status_code)

        # --- Error handling ---------------------------------------------------
        if response.status_code == 401:
            logger.error("OpenSky authentication failed (401)")
            raise OpenSkyAuthError()

        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            retry_secs = int(retry_after) if retry_after and retry_after.isdigit() else None
            logger.warning("OpenSky rate-limited (429), retry after %s s", retry_secs)
            raise OpenSkyRateLimitError(retry_after=retry_secs)

        if response.status_code != 200:
            logger.error("OpenSky API returned HTTP %d: %s", response.status_code, response.text[:200])
            raise OpenSkyAPIError(response.status_code, response.text[:200])

        # --- Parse response ---------------------------------------------------
        try:
            payload = response.json()
        except Exception:
            logger.error("OpenSky returned non-JSON response body")
            raise OpenSkyAPIError(response.status_code, "Malformed JSON in response body")

        try:
            api_response = OpenSkyStatesResponse.model_validate(payload)
        except Exception as exc:
            logger.error("Failed to validate OpenSky response envelope: %s", exc)
            raise OpenSkyAPIError(response.status_code, f"Invalid response structure: {exc}")

        vectors = api_response.parse_states()

        # --- Normalize to internal AircraftState ------------------------------
        aircraft_states: List[AircraftState] = []
        for vec in vectors:
            aircraft_states.append(
                AircraftState(
                    icao24=vec.icao24,
                    callsign=vec.callsign,
                    origin_country=vec.origin_country,
                    time_position=vec.time_position,
                    last_contact=vec.last_contact,
                    longitude=vec.longitude,
                    latitude=vec.latitude,
                    baro_altitude=vec.baro_altitude,
                    on_ground=vec.on_ground,
                    velocity=vec.velocity,
                    true_track=vec.true_track,
                    vertical_rate=vec.vertical_rate,
                    geo_altitude=vec.geo_altitude,
                    squawk=vec.squawk,
                    position_source=vec.position_source,
                    category=vec.category,
                )
            )

        logger.info(
            "OpenSky: fetched %d aircraft states in %.0f ms (api_time=%d)",
            len(aircraft_states),
            elapsed_ms,
            api_response.time,
        )
        return aircraft_states
