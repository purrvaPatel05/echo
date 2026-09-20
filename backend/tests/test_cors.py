from httpx import ASGITransport, AsyncClient

from app.main import app


async def _preflight(origin: str):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        return await client.options(
            "/referrals",
            headers={"Origin": origin, "Access-Control-Request-Method": "POST"},
        )


async def test_local_frontend_origin_is_allowed():
    r = await _preflight("http://localhost:5173")
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_unknown_origin_is_not_allowed():
    r = await _preflight("https://evil.example")
    assert "access-control-allow-origin" not in r.headers
