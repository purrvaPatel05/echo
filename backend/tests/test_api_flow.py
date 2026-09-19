from datetime import UTC, datetime, timedelta

from app.booking import SlotUnavailableError
from app.matching.rules_analyzer import RulesAnalyzer
from app.matching.service import Analyzers
from app.models.enums import FitTier
from app.models.match import ClinicalFit
from app.models.scheduling import Appointment, AppointmentSlot

KNEE, RARE_PULM = "ref_demo_knee", "ref_demo_rare_pulm"
KNEE_DOC, PULM_DOC = "doc_001", "doc_003"


async def _ready_to_match(api, referral_id=KNEE, complexity="routine"):
    assert (await api.client.post(f"/referrals/{referral_id}/parse")).status_code == 202
    r = await api.client.patch(f"/referrals/{referral_id}", json={"complexity": complexity})
    assert r.status_code == 200


async def _match(api, referral_id=KNEE):
    r = await api.client.post(f"/referrals/{referral_id}/match")
    assert r.status_code == 202
    run = (await api.client.get(f"/referrals/{referral_id}/match")).json()
    assert run["id"] == r.json()["id"]
    return run


def _approval(run, physician, specialist_id=None, slot_id=None):
    top = run["results"][0]
    return {
        "match_run_id": run["id"],
        "specialist_id": specialist_id or top["specialist"]["id"],
        "slot_id": slot_id or top["earliest_slot"]["id"],
        "approved_by": physician,
    }


async def _approve(api, referral_id, run, physician, **overrides):
    body = _approval(run, physician, **overrides)
    return await api.client.post(f"/referrals/{referral_id}/approve", json=body)


async def test_directory_and_seeded_referrals(api):
    c = api.client
    assert len((await c.get("/physicians")).json()) == 3
    assert len((await c.get("/patients")).json()) == 6
    assert len((await c.get("/specialists")).json()) == 12
    assert (await c.get("/patients/pat_001")).json()["insurance"]["payer"] == "Aetna"
    assert (await c.get("/patients/nope")).status_code == 404
    assert (await c.get("/specialists/nope")).status_code == 404
    refs = (await c.get("/referrals")).json()
    assert len(refs) == 6 and all(r["status"] == "draft" for r in refs)


async def test_create_referral_validates_patient_and_physician(api):
    body = {"patient_id": "pat_001", "referring_physician_id": "doc_001", "case_notes": "knee pain"}
    created = await api.client.post("/referrals", json=body)
    assert created.status_code == 201 and created.json()["status"] == "draft"
    for bad in ({"patient_id": "nope"}, {"referring_physician_id": "nope"}):
        r = await api.client.post("/referrals", json={**body, **bad})
        assert r.status_code == 404


async def test_full_flow_parse_confirm_match_approve(api):
    c = api.client
    assert (await c.post(f"/referrals/{KNEE}/match")).status_code == 409  # not parsed yet
    await c.post(f"/referrals/{KNEE}/parse")
    ref = (await c.get(f"/referrals/{KNEE}")).json()
    assert ref["parsed_case"]["suggested_specialties"] == ["Orthopedics"]
    assert ref["complexity"] is None
    # parsing does not confirm anything on the physician's behalf
    assert (await c.post(f"/referrals/{KNEE}/match")).status_code == 409

    await c.patch(f"/referrals/{KNEE}", json={"complexity": "routine"})
    run = await _match(api)
    assert run["status"] == "complete" and run["degraded"] is True  # rules-only, no Claude
    assert run["weight_profile"] == "routine"
    assert [r["specialist"]["id"] for r in run["results"]] == ["sp_chen", "sp_park"]
    assert (await c.get(f"/referrals/{KNEE}")).json()["status"] == "matched"

    # nothing is approved or booked until the referring physician says so
    wrong_doc = await c.post(f"/referrals/{KNEE}/approve", json=_approval(run, "doc_002"))
    assert wrong_doc.status_code == 403
    approved = await c.post(f"/referrals/{KNEE}/approve", json=_approval(run, KNEE_DOC))
    assert approved.status_code == 200
    body = approved.json()
    assert body["status"] == "approved" and body["appointment"] is None  # no booker wired in yet
    assert body["approval"]["approved_by"] == KNEE_DOC

    summary = (await c.get(f"/referrals/{KNEE}/patient-summary")).json()
    assert "Sarah Chen" in summary["summary"] and summary["cost_note"] is None


async def test_patient_summary_before_approval_promises_nothing(api):
    s = (await api.client.get(f"/referrals/{KNEE}/patient-summary")).json()
    assert s["specialist_name"] is None and "reviewing" in s["summary"]


async def test_approve_rejects_bad_requests(api):
    c = api.client
    await _ready_to_match(api)
    run = await _match(api)
    url = f"/referrals/{KNEE}/approve"
    assert (
        await c.post(url, json=_approval(run, KNEE_DOC, specialist_id="sp_okafor"))
    ).status_code == 422
    assert (
        await c.post(url, json=_approval(run, KNEE_DOC, slot_id="slot_bogus"))
    ).status_code == 422

    newer = await _match(api)  # a second run makes the first one stale
    assert newer["id"] != run["id"]
    assert (await _approve(api, KNEE, run, KNEE_DOC)).status_code == 409


async def test_editing_after_match_invalidates_it(api):
    c = api.client
    await _ready_to_match(api)
    run = await _match(api)
    await c.patch(f"/referrals/{KNEE}", json={"urgency": "urgent"})
    assert (await c.get(f"/referrals/{KNEE}")).json()["status"] == "draft"
    approve = await c.post(f"/referrals/{KNEE}/approve", json=_approval(run, KNEE_DOC))
    assert approve.status_code == 409


async def test_waitlist_then_rematch(api):
    c = api.client
    assert (await c.post(f"/referrals/{KNEE}/waitlist")).status_code == 409  # not matched yet
    await _ready_to_match(api)
    await _match(api)
    assert (await c.post(f"/referrals/{KNEE}/waitlist")).json()["status"] == "waitlisted"
    await _match(api)
    assert (await c.get(f"/referrals/{KNEE}")).json()["status"] == "matched"


class FakeBooker:
    def __init__(self, fail=False):
        self.fail, self.calls = fail, []

    async def book(self, referral, specialist_id, slot_id):
        self.calls.append((referral.id, specialist_id, slot_id))
        if self.fail:
            raise SlotUnavailableError
        start = datetime(2026, 9, 24, 9, 0, tzinfo=UTC)
        slot = AppointmentSlot(
            id=slot_id, specialist_id=specialist_id, start=start, end=start + timedelta(minutes=30)
        )
        return Appointment(id="apt_1", referral_id=referral.id, slot=slot, status="booked")


async def test_booker_seam_books_on_approval(api):
    api.state["booker"] = FakeBooker()
    await _ready_to_match(api)
    run = await _match(api)
    body = (
        await api.client.post(f"/referrals/{KNEE}/approve", json=_approval(run, KNEE_DOC))
    ).json()
    assert body["status"] == "booked" and body["appointment"]["id"] == "apt_1"
    assert api.state["booker"].calls == [
        (KNEE, "sp_chen", run["results"][0]["earliest_slot"]["id"])
    ]
    summary = (await api.client.get(f"/referrals/{KNEE}/patient-summary")).json()
    assert "Thursday, September 24" in summary["summary"]


async def test_slot_taken_at_booking_time_leaves_referral_matched(api):
    api.state["booker"] = FakeBooker(fail=True)
    await _ready_to_match(api)
    run = await _match(api)
    r = await api.client.post(f"/referrals/{KNEE}/approve", json=_approval(run, KNEE_DOC))
    assert r.status_code == 409
    ref = (await api.client.get(f"/referrals/{KNEE}")).json()
    assert ref["status"] == "matched" and ref["approval"] is None


async def test_out_of_network_choice_gets_a_cost_note(api):
    await _ready_to_match(api, RARE_PULM, complexity="rare_complex")
    run = await _match(api, RARE_PULM)
    assert run["weight_profile"] == "rare_complex"
    assert [r["specialist"]["id"] for r in run["results"]] == [
        "sp_holt",
        "sp_reyes",
    ]  # sp_lin gated
    assert run["results"][0]["insurance"]["status"] == "out_of_network"
    await api.client.post(f"/referrals/{RARE_PULM}/approve", json=_approval(run, PULM_DOC))
    summary = (await api.client.get(f"/referrals/{RARE_PULM}/patient-summary")).json()
    assert "out-of-network" in summary["cost_note"]


async def test_claude_backed_match_is_not_degraded(api):
    class Primary(RulesAnalyzer):
        async def assess_fit(self, parsed, specialists):
            fit = ClinicalFit(tier=FitTier.EXCELLENT, rationale="Scripted expert")
            return {s.id: fit for s in specialists if s.specialty == "Orthopedics"}

    api.state["analyzers"] = Analyzers(primary=Primary(), fallback=RulesAnalyzer())
    await _ready_to_match(api)
    run = await _match(api)
    assert run["degraded"] is False
    assert run["results"][0]["clinical_fit"]["rationale"] == "Scripted expert"


async def test_failed_match_is_reported_and_referral_stays_draft(api):
    class Boom:
        async def candidates_for(self, patient, specialists):
            raise RuntimeError("scheduling service down")

    api.state["provider"] = Boom()
    await _ready_to_match(api)
    run = await _match(api)
    assert run["status"] == "failed" and "logs" in run["error"]
    assert "scheduling service down" not in run["error"]  # internals aren't leaked
    assert (await api.client.get(f"/referrals/{KNEE}")).json()["status"] == "draft"
