"""Distance: Google Maps Distance Matrix API, falling back to haversine straight-line distance.

Mirrors the Claude analyzer's degrade-gracefully rule (CLAUDE.md: "Claude failure must degrade
gracefully") -- without `GOOGLE_MAPS_API_KEY`, or if the call errors, times out, or returns a
non-OK element status, distance falls back to haversine rather than breaking matching.
"""

import logging
import math

import httpx

from app.models.people import GeoPoint

logger = logging.getLogger(__name__)

_EARTH_RADIUS_MILES = 3958.8
_DISTANCE_MATRIX_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"
_METERS_PER_MILE = 1609.344


def haversine_miles(origin: GeoPoint, destination: GeoPoint) -> float:
    lat1, lat2 = math.radians(origin.lat), math.radians(destination.lat)
    dlat = lat2 - lat1
    dlng = math.radians(destination.lng - origin.lng)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    return 2 * _EARTH_RADIUS_MILES * math.asin(math.sqrt(a))


class DistanceClient:
    """`client` is an httpx.AsyncClient (or a test double with a matching `.get()`)."""

    def __init__(self, api_key: str | None, client: httpx.AsyncClient | None = None):
        self._api_key = api_key
        self._client = client or httpx.AsyncClient()

    async def distance_miles(self, origin: GeoPoint, destination: GeoPoint) -> float:
        if not self._api_key:
            return haversine_miles(origin, destination)
        try:
            response = await self._client.get(
                _DISTANCE_MATRIX_URL,
                params={
                    "origins": f"{origin.lat},{origin.lng}",
                    "destinations": f"{destination.lat},{destination.lng}",
                    "units": "imperial",
                    "key": self._api_key,
                },
            )
            response.raise_for_status()
            element = response.json()["rows"][0]["elements"][0]
            if element["status"] != "OK":
                raise ValueError(f"Distance Matrix element status: {element['status']}")
            return element["distance"]["value"] / _METERS_PER_MILE
        except Exception:
            logger.warning(
                "Google Maps distance lookup failed; falling back to haversine", exc_info=True
            )
            return haversine_miles(origin, destination)
