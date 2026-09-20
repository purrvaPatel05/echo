"""AUTH_MODE=session: demo accounts sign in and each sees only its own data."""

import time

import pytest
from pydantic import ValidationError

from app.config import Settings, settings
from app.echo import session
from app.echo.session import demo_email, issue_token, read_token

SECRET = "s" * 40
PASSWORD = "demo-pass-1"


@pytest.fixture
async def login(api, monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "session")
    monkeypatch.setattr(settings, "session_secret", SECRET)
    monkeypatch.setattr(settings, "demo_password", PASSWORD)
    monkeypatch.setattr(settings, "demo_account_login", True)
    monkeypatch.setattr(session, "limiter", session.LoginLimiter())
    monkeypatch.setattr("app.echo.router.limiter", session.limiter)
    del api.client.headers["X-Dev-Physician"]
    return api.client


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def test_config_tells_the_frontend_to_show_the_login_page(login):
    assert (await login.get("/api/echo/auth/config")).json() == {
        "login": True,
        "demoAccounts": True,
    }


async def test_demo_emails_are_predictable():
    from app.models.people import Physician

    p = Physician(
        id="doc_001",
        name="Dr. Elena Ruiz",
        specialty="x",
        practice_name="Riverside Family Practice",
    )
    assert demo_email(p) == "elena.ruiz@riverside.example"


async def test_demo_account_list_shows_the_email_that_logs_in(login):
    accounts = (await login.get("/api/echo/auth/demo-accounts")).json()
    assert accounts
    for a in accounts:
        r = await login.post(
            "/api/echo/auth/login", json={"email": a["email"], "password": PASSWORD}
        )
        assert r.status_code == 200 and r.json()["physician"]["id"] == a["id"], a


async def test_password_login_returns_a_working_token_for_that_physician(login):
    r = await login.post(
        "/api/echo/auth/login", json={"email": " Marcus.Bell@harbor.example ", "password": PASSWORD}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["physician"]["id"] == "doc_002" and body["physician"]["name"] == "Dr. Marcus Bell"
    me = await login.get("/api/echo/me", headers=_auth(body["token"]))
    assert me.status_code == 200 and me.json()["id"] == "doc_002"


async def test_wrong_password_and_unknown_email_get_the_same_answer(login):
    a = await login.post(
        "/api/echo/auth/login",
        json={"email": "marcus.bell@harbor.example", "password": "nope-nope"},
    )
    b = await login.post(
        "/api/echo/auth/login", json={"email": "nobody@nowhere.example", "password": PASSWORD}
    )
    assert (
        (a.status_code, a.json())
        == (b.status_code, b.json())
        == (401, {"detail": "Check your email and password."})
    )


async def test_guessing_is_slowed_down(login):
    for _ in range(8):
        await login.post(
            "/api/echo/auth/login",
            json={"email": "marcus.bell@harbor.example", "password": "wrong-wrong"},
        )
    blocked = await login.post(
        "/api/echo/auth/login", json={"email": "marcus.bell@harbor.example", "password": PASSWORD}
    )
    assert blocked.status_code == 429  # even the right password waits


async def test_every_other_route_needs_a_valid_token(login):
    assert (await login.get("/api/echo/me")).status_code == 401
    assert (await login.get("/api/echo/me", headers=_auth("garbage"))).status_code == 401
    assert (
        await login.get("/api/echo/me", headers={"X-Dev-Physician": "doc_001"})
    ).status_code == 401  # no header trick
    good = issue_token("doc_001")
    tampered = good[:-2] + ("aa" if not good.endswith("aa") else "bb")
    assert (await login.get("/api/echo/me", headers=_auth(tampered))).status_code == 401
    assert (await login.get("/api/echo/referrals", headers=_auth(good))).status_code == 200


async def test_an_expired_token_is_refused(login):
    old = issue_token("doc_001", now=time.time() - 13 * 3600)  # 12h lifetime
    assert read_token(old) is None
    assert (await login.get("/api/echo/me", headers=_auth(old))).status_code == 401


async def test_each_account_sees_only_its_own_referrals_and_conversations(login):
    ruiz = _auth(
        (await login.post("/api/echo/auth/demo-login", json={"physicianId": "doc_001"})).json()[
            "token"
        ]
    )
    bell = _auth(
        (await login.post("/api/echo/auth/demo-login", json={"physicianId": "doc_002"})).json()[
            "token"
        ]
    )
    mine = {r["id"] for r in (await login.get("/api/echo/referrals", headers=ruiz)).json()}
    theirs = {r["id"] for r in (await login.get("/api/echo/referrals", headers=bell)).json()}
    assert mine and theirs and not (mine & theirs)
    assert (
        await login.get(f"/api/echo/referrals/{next(iter(theirs))}", headers=ruiz)
    ).status_code == 404
    # Real two-sided chat: Ruiz writes to Bell; Bell sees it and answers; Ruiz sees the answer.
    t = (
        await login.post(
            "/api/echo/consults", headers=ruiz, json={"colleagueId": "doc_002", "text": "Hi Marcus"}
        )
    ).json()
    assert [x["id"] for x in (await login.get("/api/echo/consults", headers=bell)).json()] == [
        t["id"]
    ]
    await login.post(
        f"/api/echo/consults/{t['id']}/messages", headers=bell, json={"text": "Hi Elena"}
    )
    seen = (await login.get(f"/api/echo/consults/{t['id']}", headers=ruiz)).json()
    assert [(m["fromMe"], m["text"]) for m in seen["messages"]] == [
        (True, "Hi Marcus"),
        (False, "Hi Elena"),
    ]
    assert seen["colleague"]["id"] == "doc_002"


async def test_demo_login_is_off_unless_enabled_and_needs_a_real_physician(login, monkeypatch):
    assert (
        await login.post("/api/echo/auth/demo-login", json={"physicianId": "nope"})
    ).status_code == 404
    monkeypatch.setattr(settings, "demo_account_login", False)
    assert (
        await login.post("/api/echo/auth/demo-login", json={"physicianId": "doc_001"})
    ).status_code == 404
    assert (await login.get("/api/echo/auth/demo-accounts")).status_code == 404
    assert (await login.get("/api/echo/auth/config")).json() == {
        "login": True,
        "demoAccounts": False,
    }


async def test_login_endpoints_do_nothing_outside_session_mode(api):
    assert (await api.client.get("/api/echo/auth/config")).json() == {
        "login": False,
        "demoAccounts": False,
    }
    r = await api.client.post(
        "/api/echo/auth/login", json={"email": "a@b.example", "password": "whatever1"}
    )
    assert r.status_code == 404


def test_session_mode_needs_a_secret_and_a_way_to_sign_in():
    with pytest.raises(ValidationError, match="SESSION_SECRET"):
        Settings(_env_file=None, auth_mode="session", demo_password=PASSWORD)
    with pytest.raises(ValidationError, match="DEMO_PASSWORD"):
        Settings(_env_file=None, auth_mode="session", session_secret=SECRET)
    assert Settings(
        _env_file=None, auth_mode="session", session_secret=SECRET, demo_password=PASSWORD
    )
    assert Settings(
        _env_file=None, auth_mode="session", session_secret=SECRET, demo_account_login=True
    )


def test_tokens_are_signed_with_the_secret(monkeypatch):
    monkeypatch.setattr(settings, "session_secret", SECRET)
    token = issue_token("doc_003")
    assert read_token(token) == "doc_003"
    monkeypatch.setattr(settings, "session_secret", "x" * 40)  # a different secret cannot read it
    assert read_token(token) is None
