"""Deployment safety: production refuses unsafe settings, and demo auth is explicit and closed.

These build `Settings` directly (no environment), so they don't depend on a developer's .env.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from app.config import Settings
from app.main import app

BACKEND = Path(__file__).resolve().parents[1]
GOOD_DB = "postgresql+asyncpg://echo_app:S3cure-pw@db.example.com:5432/echo?ssl=require"
TOKEN = "t" * 32


def prod(**overrides) -> Settings:
    base = dict(
        environment="production",
        auth_mode="auth0",
        auth0_domain="t.us.auth0.com",
        auth0_audience="https://api.example",
        database_url=GOOD_DB,
        cors_origins=["https://echo.example.com"],
    )
    return Settings(_env_file=None, **{**base, **overrides})


# ---- .env.example --------------------


def _example_names() -> set[str]:
    text = (BACKEND / ".env.example").read_text()
    names = set(re.findall(r"^#?\s*([A-Z][A-Z0-9_]*)=", text, flags=re.MULTILINE))
    return {
        n for n in names if not n.startswith("VITE_")
    }  # frontend build variable, noted in the header


def test_env_example_documents_every_setting_and_only_real_ones():
    fields = {name.upper() for name in Settings.model_fields}
    names = _example_names()
    assert names <= fields, f"not settings: {sorted(names - fields)}"
    assert fields <= names, f"undocumented settings: {sorted(fields - names)}"


def test_env_example_holds_no_secret_values():
    text = (BACKEND / ".env.example").read_text()
    for key in ("ANTHROPIC_API_KEY", "GOOGLE_MAPS_API_KEY", "DEMO_ACCESS_TOKEN"):
        assert not re.search(rf"^{key}=\S", text, flags=re.MULTILINE), f"{key} has a value"
    assert not re.search(r"sk-ant-|AIza", text)


def test_env_example_loads_as_written(monkeypatch):
    for name in _example_names():
        monkeypatch.delenv(name, raising=False)
    s = Settings(_env_file=BACKEND / ".env.example")
    assert s.environment == "development" and s.auth_mode == "dev"


# ---- production refuses unsafe settings --------------------


def test_a_safe_production_configuration_loads():
    assert prod().environment == "production"


@pytest.mark.parametrize(
    "overrides, message",
    [
        (dict(auth_mode="dev"), "AUTH_MODE=dev"),
        (dict(database_url="sqlite+aiosqlite:///./echo.db"), "asyncpg"),
        (dict(database_url="postgresql+asyncpg://echo:echo@db.example.com/echo"), "own password"),
        (dict(database_url="postgresql+asyncpg://u:strong-pw@localhost/echo"), "real database"),
        (dict(auth0_domain=None), "AUTH0_DOMAIN"),
        (dict(cors_origins=["*"]), "CORS_ORIGINS"),
    ],
)
def test_production_refuses_unsafe_settings(overrides, message):
    with pytest.raises(ValidationError, match=message):
        prod(**overrides)


def test_production_can_use_demo_auth_but_it_needs_a_long_token():
    assert prod(auth_mode="demo", demo_access_token=TOKEN).auth_mode == "demo"
    for token in (None, "", "short"):
        with pytest.raises(ValidationError, match="DEMO_ACCESS_TOKEN"):
            prod(auth_mode="demo", demo_access_token=token)
    with pytest.raises(ValidationError, match="DEMO_ACCESS_TOKEN"):  # in any environment
        Settings(_env_file=None, auth_mode="demo", demo_access_token="short")


def test_the_default_mode_is_the_closed_one():
    s = Settings(_env_file=None)
    assert s.auth_mode == "auth0" and s.environment == "development"


def test_production_hides_the_api_docs():
    code = "from app.main import app; print(app.docs_url, app.redoc_url, app.openapi_url)"
    env = {
        "ENVIRONMENT": "production",
        "AUTH_MODE": "auth0",
        "AUTH0_DOMAIN": "t.us.auth0.com",
        "AUTH0_AUDIENCE": "https://api.example",
        "DATABASE_URL": GOOD_DB,
        "CORS_ORIGINS": '["https://echo.example.com"]',
        "SIMULATE_COLLEAGUE_REPLIES": "false",  # backend/.env may enable it locally
        "PATH": "/usr/bin:/bin",
    }
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=BACKEND, env=env, capture_output=True, text=True
    )
    assert out.returncode == 0, out.stderr
    assert out.stdout.strip() == "None None None"
    assert (app.docs_url, app.openapi_url) == ("/docs", "/openapi.json")  # development keeps them


# ---- demo auth: explicit, token-gated, and closed everywhere else --------------------


@pytest.fixture
async def demo(api, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "auth_mode", "demo")
    monkeypatch.setattr(settings, "demo_access_token", TOKEN)
    monkeypatch.setattr(settings, "demo_physician_id", "doc_001")
    del api.client.headers["X-Dev-Physician"]  # the browser sends none
    return api.client


async def test_demo_mode_needs_the_access_token(demo):
    assert (await demo.get("/api/echo/me")).status_code == 401
    assert (await demo.get("/api/echo/me", headers={"X-Demo-Access": "wrong"})).status_code == 401
    assert (
        await demo.get("/api/echo/me", headers={"X-Demo-Access": TOKEN[:-1]})
    ).status_code == 401
    ok = await demo.get("/api/echo/me", headers={"X-Demo-Access": TOKEN})
    assert ok.status_code == 200 and ok.json()["id"] == "doc_001"


async def test_demo_mode_ignores_a_client_chosen_identity(demo):
    headers = {"X-Demo-Access": TOKEN, "X-Dev-Physician": "doc_003"}  # trying to be someone else
    assert (await demo.get("/api/echo/me", headers=headers)).json()["id"] == "doc_001"
    assert (
        await demo.get("/api/echo/me", headers={"X-Dev-Physician": "doc_001"})
    ).status_code == 401


async def test_demo_mode_leaves_the_core_api_closed(demo):
    headers = {"X-Demo-Access": TOKEN, "X-Dev-Physician": "doc_001"}
    for path in ("/referrals", "/patients", "/physicians", "/consults"):
        r = await demo.get(path, headers=headers)
        assert r.status_code in (401, 503), (path, r.status_code)


async def test_demo_mode_works_end_to_end_for_the_frontends_calls(demo):
    h = {"X-Demo-Access": TOKEN}
    assert len((await demo.get("/api/echo/referrals", headers=h)).json()) >= 1
    assert (await demo.get("/api/echo/patients", headers=h)).status_code == 200
    assert (await demo.get("/api/echo/referral-options", headers=h)).status_code == 200


async def test_dev_default_physician_does_not_apply_outside_dev(api, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "auth_mode", "auth0")
    monkeypatch.setattr(settings, "auth0_domain", "t.us.auth0.com")
    monkeypatch.setattr(settings, "auth0_audience", "https://api.example")
    del api.client.headers["X-Dev-Physician"]
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        assert (await c.get("/api/echo/me")).status_code == 401
        assert (await c.get("/api/echo/me", headers={"X-Demo-Access": TOKEN})).status_code == 401
