"""Authentication and authorization: token verification, roles, ownership scoping.

Tokens are signed with a throwaway RSA key generated here; `app.auth._signing_key` is pointed at
its public half, so no Auth0 tenant or network is needed.
"""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app import auth
from app.config import settings
from app.main import app

DOMAIN, AUDIENCE, NS = "echo-test.us.auth0.com", "https://api.echo.test", "https://echo"
KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _token(physician_id="doc_001", roles=("referring_physician",), *, key=KEY, **overrides):
    claims = {
        "iss": f"https://{DOMAIN}/",
        "aud": AUDIENCE,
        "sub": f"auth0|{physician_id}",
        "exp": int(time.time()) + 600,
        f"{NS}/physician_id": physician_id,
        f"{NS}/roles": list(roles),
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "test"})


def _bearer(**kw) -> dict:
    return {"Authorization": f"Bearer {_token(**kw)}"}


@pytest.fixture
def auth0_mode(monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "auth0")
    monkeypatch.setattr(settings, "auth0_domain", DOMAIN)
    monkeypatch.setattr(settings, "auth0_audience", AUDIENCE)
    monkeypatch.setattr(auth, "_signing_key", lambda token: KEY.public_key())


# ---- token verification --------------------------------------------------------------------


async def test_valid_token_is_accepted(api, auth0_mode):
    r = await api.client.get("/referrals", headers=_bearer())
    assert r.status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        {},  # no token
        {"Authorization": "Bearer not-a-jwt"},
        {"Authorization": f"Bearer {_token(exp=int(time.time()) - 10)}"},  # expired
        {"Authorization": f"Bearer {_token(aud='https://someone-else')}"},  # wrong audience
        {"Authorization": f"Bearer {_token(iss='https://evil.example/')}"},  # wrong issuer
        {"Authorization": f"Bearer {_token(key=OTHER_KEY)}"},  # signed with the wrong key
        {"Authorization": f"Bearer {_token(exp=None)}"},  # no expiry
    ],
    ids=["missing", "garbage", "expired", "audience", "issuer", "wrong-key", "no-exp"],
)
async def test_bad_tokens_get_401(api, auth0_mode, headers):
    api.client.headers.pop("X-Dev-Physician", None)
    r = await api.client.get("/referrals", headers=headers)
    assert r.status_code == 401
    assert r.headers["www-authenticate"] == "Bearer"


async def test_dev_header_is_ignored_in_auth0_mode(api, auth0_mode):
    r = await api.client.get("/referrals", headers={"X-Dev-Physician": "doc_001"})
    assert r.status_code == 401


async def test_unconfigured_auth0_mode_fails_closed(api, monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "auth0")
    monkeypatch.setattr(settings, "auth0_domain", None)
    monkeypatch.setattr(settings, "auth0_audience", None)
    r = await api.client.get("/referrals", headers=_bearer())
    assert r.status_code == 503


async def test_health_needs_no_login(api, auth0_mode):
    api.client.headers.pop("X-Dev-Physician", None)
    assert (await api.client.get("/health")).status_code == 200


# ---- roles ---------------------------------------------------------------------------------


async def test_account_not_linked_to_a_physician_is_forbidden(api, auth0_mode):
    r = await api.client.get("/referrals", headers=_bearer(physician_id=None))
    assert r.status_code == 403


async def test_specialist_role_has_no_access_yet(api, auth0_mode):
    r = await api.client.get("/referrals", headers=_bearer(roles=("specialist",)))
    assert r.status_code == 403


# ---- ownership scoping and identity --------------------------------------------------------


async def test_physicians_only_see_their_own_referrals(api, auth0_mode):
    c = api.client
    mine = (await c.get("/referrals", headers=_bearer(physician_id="doc_003"))).json()
    assert {r["id"] for r in mine} == {"ref_demo_rare_pulm", "ref_demo_derm"}
    someone_elses = "ref_demo_knee"  # doc_001's
    for method, path in (
        ("get", f"/referrals/{someone_elses}"),
        ("patch", f"/referrals/{someone_elses}"),
        ("post", f"/referrals/{someone_elses}/parse"),
        ("post", f"/referrals/{someone_elses}/match"),
        ("get", f"/referrals/{someone_elses}/match"),
        ("post", f"/referrals/{someone_elses}/waitlist"),
        ("get", f"/referrals/{someone_elses}/patient-summary"),
        ("get", f"/referrals/{someone_elses}/trials"),
    ):
        r = await c.request(method, path, headers=_bearer(physician_id="doc_003"), json={})
        assert r.status_code == 404, (method, path)  # existence is not revealed


async def test_admin_sees_everything_but_cannot_approve_for_someone(api, auth0_mode):
    c = api.client
    admin = _bearer(physician_id="doc_002", roles=("admin",))
    assert len((await c.get("/referrals", headers=admin)).json()) == 6
    assert (await c.get("/referrals/ref_demo_knee", headers=admin)).status_code == 200
    body = {"match_run_id": "m", "specialist_id": "sp_chen", "slot_id": "s"}
    r = await c.post("/referrals/ref_demo_knee/approve", json=body, headers=admin)
    assert r.status_code == 403  # approval stays with the referring physician


async def test_identity_comes_from_the_token_not_the_body(api, auth0_mode):
    c = api.client
    referral = {"patient_id": "pat_001", "case_notes": "knee pain"}
    created = await c.post("/referrals", json=referral, headers=_bearer(physician_id="doc_002"))
    assert created.status_code == 201
    assert created.json()["referring_physician_id"] == "doc_002"

    spoof = {**referral, "referring_physician_id": "doc_001"}
    r = await c.post("/referrals", json=spoof, headers=_bearer(physician_id="doc_002"))
    assert r.status_code == 403


async def test_approval_is_recorded_against_the_token_identity(api, auth0_mode):
    c = api.client
    h = _bearer(physician_id="doc_001")
    await c.post("/referrals/ref_demo_knee/parse", headers=h)
    await c.patch("/referrals/ref_demo_knee", json={"complexity": "routine"}, headers=h)
    await c.post("/referrals/ref_demo_knee/match", headers=h)
    run = (await c.get("/referrals/ref_demo_knee/match", headers=h)).json()
    top = run["results"][0]
    body = {
        "match_run_id": run["id"],
        "specialist_id": top["specialist"]["id"],
        "slot_id": top["earliest_slot"]["id"],
    }
    spoof = await c.post(
        "/referrals/ref_demo_knee/approve", headers=h, json={**body, "approved_by": "doc_002"}
    )
    assert spoof.status_code == 403
    ok = await c.post("/referrals/ref_demo_knee/approve", headers=h, json=body)  # no approved_by
    assert ok.status_code == 200
    assert ok.json()["approval"]["approved_by"] == "doc_001"


async def test_directory_needs_a_login(api, auth0_mode):
    api.client.headers.pop("X-Dev-Physician", None)
    for path in ("/physicians", "/patients", "/specialists"):
        assert (await api.client.get(path)).status_code == 401
        assert (await api.client.get(path, headers=_bearer())).status_code == 200


async def test_consult_identity_and_privacy(api, auth0_mode):
    c = api.client
    start = {"to_physician_id": "doc_002", "body": "hello"}
    r = await c.post("/consults", json=start, headers=_bearer(physician_id="doc_001"))
    assert r.status_code == 201
    assert r.json()["initiator_physician_id"] == "doc_001"
    thread_id = r.json()["id"]

    spoof = await c.post(
        "/consults", json={**start, "from_physician_id": "doc_003"}, headers=_bearer()
    )
    assert spoof.status_code == 403
    peek = await c.get("/consults", params={"physician_id": "doc_002"}, headers=_bearer())
    assert peek.status_code == 403
    outsider = _bearer(physician_id="doc_003")
    assert (await c.get(f"/consults/{thread_id}/messages", headers=outsider)).status_code == 403
    # a referral you don't own can't be attached as consult context
    other = await c.post(
        "/consults",
        json={**start, "referral_id": "ref_demo_rare_pulm"},
        headers=_bearer(physician_id="doc_001"),
    )
    assert other.status_code == 404
    # the recipient sees the thread, without passing their own id
    inbox = await c.get("/consults", headers=_bearer(physician_id="doc_002"))
    assert [t["id"] for t in inbox.json()] == [thread_id]


# ---- WebSocket -----------------------------------------------------------------------------


def _ws_rejected(client: TestClient, url: str) -> bool:
    from starlette.websockets import WebSocketDisconnect

    try:
        with client.websocket_connect(url):
            return False
    except WebSocketDisconnect:
        return True


def test_websocket_requires_a_valid_token_for_your_own_id(auth0_mode):
    from app.deps import get_redis

    app.dependency_overrides[get_redis] = lambda: None  # never reached for rejected sockets
    try:
        client = TestClient(app)
        assert _ws_rejected(client, "/ws/consults/doc_001")  # no token
        assert _ws_rejected(client, "/ws/consults/doc_001?token=garbage")
        good = _token(physician_id="doc_002")
        assert _ws_rejected(client, f"/ws/consults/doc_001?token={good}")  # someone else's inbox
    finally:
        del app.dependency_overrides[get_redis]
