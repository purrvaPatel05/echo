import pytest
from fastapi.testclient import TestClient

from app import store
from app.main import api

client = TestClient(api)


@pytest.fixture(autouse=True)
def _reset():
    store.reset()


def _make_case(notes="Suspected heart failure, elevated BNP, dyspnea", urgency="routine"):
    r = client.post("/api/cases", json={
        "title": "t", "patient_age": 60, "patient_sex": "F", "urgency": urgency, "notes": notes,
    })
    assert r.status_code == 201
    return r.json()


def test_health():
    assert client.get("/api/health").json() == {"status": "ok"}


def test_match_cardiology_excludes_closed_specialists():
    case = _make_case()
    r = client.post("/api/cases/%s/match" % case["id"]).json()
    assert r["parsed"]["specialty"] == "Cardiology"
    ids = [m["specialist"]["id"] for m in r["specialists"]]
    assert "s_1" in ids
    assert "s_4" not in ids  # not accepting referrals -> guardrail drops it
    assert all(m["specialist"]["specialty"] == "Cardiology" for m in r["specialists"])


def test_emergent_urgency_limits_distance():
    case = _make_case(urgency="emergent")
    r = client.post("/api/cases/%s/match" % case["id"]).json()
    assert all(m["distance_km"] <= 150 for m in r["specialists"])


def test_referral_and_booking_flow():
    case = _make_case()
    ref = client.post("/api/referrals", json={"case_id": case["id"], "specialist_id": "s_1"}).json()
    assert ref["status"] == "pending"
    slot = client.get("/api/specialists/s_1/slots").json()[0]
    booked = client.post("/api/appointments", json={"referral_id": ref["id"], "slot_id": slot["id"]}).json()
    assert booked["status"] == "scheduled"
    again = client.post("/api/appointments", json={"referral_id": ref["id"], "slot_id": slot["id"]})
    assert again.status_code == 409
