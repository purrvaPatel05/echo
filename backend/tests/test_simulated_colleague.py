"""The demo colleague: answers chat messages with a labelled canned reply.

Enabled by SIMULATE_COLLEAGUE_REPLIES.
"""

import pytest
from pydantic import ValidationError

from app.config import Settings, settings
from app.echo.simulation import REPLIES, reply_text


@pytest.fixture
def simulate(monkeypatch):
    monkeypatch.setattr(settings, "simulate_colleague_replies", True)
    monkeypatch.setattr(settings, "simulated_reply_delay_seconds", 0)


async def _start(c, text="MRI first?", colleague="doc_002", referral=None):
    body = {
        "colleagueId": colleague,
        "text": text,
        **({"referralId": referral} if referral else {}),
    }
    r = await c.post("/api/echo/consults", json=body)
    assert r.status_code == 201, r.text
    return r.json()


async def test_off_by_default_nobody_answers(api):
    t = await _start(api.client)
    got = (await api.client.get(f"/api/echo/consults/{t['id']}")).json()
    assert len(got["messages"]) == 1 and got["status"] == "pending"


async def test_the_colleague_answers_and_the_reply_is_marked_as_a_demo(api, simulate):
    t = await _start(api.client)
    got = (await api.client.get(f"/api/echo/consults/{t['id']}")).json()
    assert [(m["fromMe"], m["simulated"]) for m in got["messages"]] == [
        (True, False),
        (False, True),
    ]
    assert got["messages"][1]["text"] == REPLIES[0]
    assert got["status"] == "responded" and got["lastMessage"]["fromMe"] is False
    # It really is the colleague in the core thread, and it is not mine.
    core = (await api.client.get(f"/consults/{t['id']}/messages")).json()
    assert core[-1]["sender_physician_id"] == "doc_002"


async def test_a_back_and_forth_gets_a_new_reply_each_time_and_never_answers_itself(api, simulate):
    c = api.client
    t = await _start(c)
    for i in range(1, 5):
        r = await c.post(f"/api/echo/consults/{t['id']}/messages", json={"text": f"follow-up {i}"})
        assert r.status_code == 201
    got = (await c.get(f"/api/echo/consults/{t['id']}")).json()
    assert [m["fromMe"] for m in got["messages"]] == [True, False] * 5  # strictly alternating
    assert [m["text"] for m in got["messages"] if m["simulated"]] == [
        reply_text(n) for n in range(1, 6)
    ]
    assert all(not m["simulated"] for m in got["messages"] if m["fromMe"])


async def test_a_reply_is_not_written_when_the_send_fails_or_the_text_is_blank(api, simulate):
    c = api.client
    assert (
        await c.post("/api/echo/consults", json={"colleagueId": "doc_002", "text": " "})
    ).status_code == 422
    assert (
        await c.post("/api/echo/consults", json={"colleagueId": "nope", "text": "hi"})
    ).status_code == 404
    assert (
        await c.get("/api/echo/consults")
    ).json() == []  # nothing was created, so nobody answered


async def test_the_list_shows_the_reply_as_the_last_message(api, simulate):
    await _start(api.client, text="Question?")
    row = (await api.client.get("/api/echo/consults")).json()[0]
    assert row["status"] == "responded" and row["lastMessage"]["text"] == REPLIES[0]


def test_the_reply_texts_give_no_medical_advice():
    joined = " ".join(REPLIES).lower()
    for word in ("mg", "dose", "prescribe", "diagnos", "surgery", "recommend", "should start"):
        assert word not in joined


def test_it_is_refused_with_real_logins():
    with pytest.raises(ValidationError, match="SIMULATE_COLLEAGUE_REPLIES"):
        Settings(_env_file=None, auth_mode="auth0", simulate_colleague_replies=True)
    assert Settings(
        _env_file=None, auth_mode="dev", simulate_colleague_replies=True
    ).simulate_colleague_replies
    demo = Settings(
        _env_file=None,
        auth_mode="demo",
        demo_access_token="t" * 32,
        simulate_colleague_replies=True,
    )
    assert demo.simulate_colleague_replies
