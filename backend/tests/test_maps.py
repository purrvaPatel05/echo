import httpx
import pytest

from app.integrations.maps import DistanceClient, haversine_miles
from app.models.people import GeoPoint

CAMBRIDGE = GeoPoint(lat=42.3736, lng=-71.1097)
BOSTON = GeoPoint(lat=42.3505, lng=-71.0810)


def test_haversine_is_zero_for_same_point():
    assert haversine_miles(CAMBRIDGE, CAMBRIDGE) == pytest.approx(0.0, abs=1e-9)


def test_haversine_matches_known_distance():
    # Cambridge <-> Boston (Back Bay) is roughly 2-3 miles as the crow flies.
    miles = haversine_miles(CAMBRIDGE, BOSTON)
    assert 1.5 < miles < 4.0


async def test_no_api_key_uses_haversine():
    client = DistanceClient(api_key=None)
    miles = await client.distance_miles(CAMBRIDGE, BOSTON)
    assert miles == pytest.approx(haversine_miles(CAMBRIDGE, BOSTON))


class _FakeTransport(httpx.AsyncBaseTransport):
    def __init__(self, handler):
        self._handler = handler

    async def handle_async_request(self, request):
        return self._handler(request)


def _google_ok(meters: float) -> httpx.AsyncClient:
    def handler(request):
        return httpx.Response(
            200, json={"rows": [{"elements": [{"status": "OK", "distance": {"value": meters}}]}]}
        )

    return httpx.AsyncClient(transport=_FakeTransport(handler))


def _google_element_status(status: str) -> httpx.AsyncClient:
    def handler(request):
        return httpx.Response(200, json={"rows": [{"elements": [{"status": status}]}]})

    return httpx.AsyncClient(transport=_FakeTransport(handler))


def _google_http_error() -> httpx.AsyncClient:
    def handler(request):
        return httpx.Response(500, text="boom")

    return httpx.AsyncClient(transport=_FakeTransport(handler))


async def test_api_key_uses_google_maps_distance():
    client = DistanceClient(api_key="fake-key", client=_google_ok(8046.72))  # 5 miles in meters
    miles = await client.distance_miles(CAMBRIDGE, BOSTON)
    assert miles == pytest.approx(5.0, rel=1e-6)


async def test_non_ok_element_status_falls_back_to_haversine():
    client = DistanceClient(api_key="fake-key", client=_google_element_status("ZERO_RESULTS"))
    miles = await client.distance_miles(CAMBRIDGE, BOSTON)
    assert miles == pytest.approx(haversine_miles(CAMBRIDGE, BOSTON))


async def test_http_error_falls_back_to_haversine():
    client = DistanceClient(api_key="fake-key", client=_google_http_error())
    miles = await client.distance_miles(CAMBRIDGE, BOSTON)
    assert miles == pytest.approx(haversine_miles(CAMBRIDGE, BOSTON))
