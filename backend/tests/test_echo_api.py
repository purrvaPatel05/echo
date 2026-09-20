"""The /api/echo/* compatibility layer: the contract the ECHO frontend is built against
(docs/echo-api-contract-changes.md), exercised through the real app with the real
provider + booker, on the seeded demo data."""

import pytest

from app.candidates import RealCandidateProvider
from app.config import settings
from app.scheduling.booker import DbBooker


class FakeDistanceClient:
    async def distance_miles(self, origin, destination):
        return 5.0


@pytest.fixture
async def echo(api):
    api.state["provider"] = RealCandidateProvider(api.factory, FakeDistanceClient())
    api.state["booker"] = DbBooker(api.factory)
    return api


KNEE_FORM = {
    "patientId": "pat_001",
    "patientLocation": "Cambridge, MA",
    "insurance": "Aetna",
    "specialty": "Orthopedics",
    "subspecialty": "Knee",
    "preferredDistanceMiles": 25,
    "urgency": "soon",
    "reason": "Knee pain, suspected meniscal tear",
    "details": "Right knee pain for 6 weeks after a twisting injury. Locking and swelling on stairs.",
}

RARE_FORM = {
    **KNEE_FORM,
    "patientId": "pat_004",
    "patientLocation": "Cambridge, MA",
    "insurance": "Medicare",
    "specialty": "Neurology",
    "subspecialty": None,
    "urgency": "routine",
    "reason": "Progressive proximal muscle weakness",
    "details": "Myopathy suspected: muscle weakness with elevated CK, neuromuscular workup pending.",
}


async def _create(api, form=KNEE_FORM):
    r = await api.client.post("/api/echo/referrals", json=form)
    assert r.status_code == 201, r.text
    return r.json()


# ---- directory ---------------------------------------------------------------------------------


async def test_directory_shapes(echo):
    c = echo.client
    me = (await c.get("/api/echo/me")).json()
    assert me == {
        "id": "doc_001",
        "name": "Dr. Elena Ruiz",
        "specialty": "Family Medicine",
        "organization": "Riverside Family Practice",
    }
    patients = (await c.get("/api/echo/patients")).json()
    assert len(patients) == 6
    maria = next(p for p in patients if p["id"] == "pat_001")
    assert maria == {
        "id": "pat_001",
        "name": "Maria Lopez",
        "age": 58,
        "sex": "F",
        "insurance": "Aetna",
        "location": "Cambridge, MA",
    }
    options = (await c.get("/api/echo/referral-options")).json()
    assert options["distancesMiles"] == [10, 25, 50, 100]
    ortho = next(s for s in options["specialties"] if s["name"] == "Orthopedics")
    assert "Knee" in ortho["subspecialties"]
    assert {"Aetna", "Medicare"} <= set(options["insurers"])
    colleagues = (await c.get("/api/echo/colleagues")).json()
    assert {x["id"] for x in colleagues} == {"doc_002", "doc_003"}  # never yourself
    assert set(colleagues[0]) == {"id", "name", "specialty", "organization"}


# ---- create, analysis, matches, select, approve ---------------------------------------------------


async def test_create_saves_first_then_analyzes_and_matches(echo):
    c = echo.client
    ref = await _create(echo)
    assert ref["status"] == "awaiting_approval"
    assert ref["reason"] == KNEE_FORM["reason"] and ref["details"] == KNEE_FORM["details"]
    assert ref["preferredDistanceMiles"] == 25 and ref["subspecialty"] == "Knee"
    assert ref["urgency"] == "soon" and ref["specialist"] is None and ref["appointmentAt"] is None
    assert ref["patient"]["sex"] == "F" and ref["patientConfirmation"] == {
        "status": "pending",
        "respondedAt": None,
    }
    assert [e["kind"] for e in ref["timeline"]] == ["created"]
    # Saved: it is on the dashboard list right away.
    assert ref["id"] in {r["id"] for r in (await c.get("/api/echo/referrals")).json()}

    snap = (await c.get(f"/api/echo/referrals/{ref['id']}/analysis")).json()
    assert snap["status"] == "complete" and snap["matchCount"] >= 1
    assert [k["key"] for k in snap["checks"]] == [
        "clinical_fit",
        "insurance",
        "distance",
        "urgency",
        "availability",
    ]
    assert all(k["state"] == "done" for k in snap["checks"])

    got = (await c.get(f"/api/echo/referrals/{ref['id']}")).json()
    assert "matches_found" in [e["kind"] for e in got["timeline"]]

    res = (await c.get(f"/api/echo/referrals/{ref['id']}/matches")).json()
    assert res["referralId"] == ref["id"] and res["searchDistanceMiles"] == 25
    assert 1 <= len(res["matches"]) <= 3 and res["noMatchReason"] is None
    m = res["matches"][0]
    assert m["strength"] in {"strong", "good", "partial"}
    assert [f["key"] for f in m["factors"]] == [
        "clinical_fit",
        "insurance",
        "distance",
        "availability",
        "urgency",
    ]
    assert all(f["status"] in {"met", "partial", "unmet"} and f["detail"] for f in m["factors"])
    assert m["nextSlot"]["id"] and m["nextSlot"]["startsAt"]
    assert m["specialist"]["city"] and m["specialist"]["organization"]
    # A label, never a number: the response must not carry a score or percent.
    assert not {"score", "matchPercent", "match_percent"} & set(m)
    assert "%" not in m["why"] and "best" not in m["why"].lower()


async def test_unknown_referral_is_404(echo):
    c = echo.client
    for path in ("", "/analysis", "/matches", "/trials", "/trials/criteria"):
        r = await c.get(f"/api/echo/referrals/nope{path}")
        assert r.status_code == 404, path
    assert (
        await c.post("/api/echo/referrals/nope/select", json={"specialistId": "sp_chen"})
    ).status_code == 404


async def test_matches_options_widen_and_partial(echo):
    c = echo.client
    ref = await _create(echo)
    base = (await c.get(f"/api/echo/referrals/{ref['id']}/matches?distanceMiles=50")).json()
    assert base["searchDistanceMiles"] == 50
    partial = (await c.get(f"/api/echo/referrals/{ref['id']}/matches?includePartial=true")).json()
    assert len(partial["matches"]) >= len(
        (await c.get(f"/api/echo/referrals/{ref['id']}/matches")).json()["matches"]
    )
    # every listed-by-default match has all factors met; partial-only entries are labelled partial
    default = (await c.get(f"/api/echo/referrals/{ref['id']}/matches")).json()["matches"]
    assert all(f["status"] == "met" for m in default for f in m["factors"])
    assert all(m["strength"] in {"strong", "good"} for m in default)


async def test_select_then_approve_books_and_is_retry_safe(echo):
    c = echo.client
    ref = await _create(echo)
    rid = ref["id"]
    top = (await c.get(f"/api/echo/referrals/{rid}/matches")).json()["matches"][0]
    sp = top["specialist"]["id"]

    sel = (await c.post(f"/api/echo/referrals/{rid}/select", json={"specialistId": sp})).json()
    assert sel["specialist"]["id"] == sp and sel["status"] == "awaiting_approval"
    assert "specialist_selected" in [e["kind"] for e in sel["timeline"]]
    assert sel["appointmentAt"] is None  # selecting books nothing
    assert (
        await c.post(f"/api/echo/referrals/{rid}/select", json={"specialistId": "nope"})
    ).status_code == 404

    slots = (await c.get(f"/api/echo/specialists/{sp}/slots")).json()
    assert len(slots) > 1 and slots == sorted(slots, key=lambda s: s["startsAt"])
    assert set(slots[0]) == {"id", "startsAt"}
    chosen = slots[1]  # not the earliest: the frontend's Appointment select may pick any open slot

    body = {"specialistId": sp, "slotId": chosen["id"]}
    booked = await c.post(f"/api/echo/referrals/{rid}/approve", json=body)
    assert booked.status_code == 200, booked.text
    b = booked.json()
    assert b["status"] == "scheduled" and b["specialist"]["id"] == sp
    assert b["appointmentAt"] == chosen["startsAt"] or b["appointmentAt"].startswith(
        chosen["startsAt"][:16]
    )
    kinds = [e["kind"] for e in b["timeline"]]
    assert {"approved", "sent_to_patient", "scheduled"} <= set(kinds)
    assert kinds.index("specialist_selected") < kinds.index("approved")
    assert b["insuranceAccepted"] in (True, False)

    # The same request again (a retry after a lost response) succeeds and books nothing twice.
    again = await c.post(f"/api/echo/referrals/{rid}/approve", json=body)
    assert again.status_code == 200 and again.json()["appointmentAt"] == b["appointmentAt"]
    # The booked slot is no longer offered.
    left = (await c.get(f"/api/echo/specialists/{sp}/slots")).json()
    assert chosen["id"] not in {s["id"] for s in left}


async def test_taken_slot_is_409_and_nothing_books(echo):
    c = echo.client
    first, second = await _create(echo), await _create(echo)
    sp = (await c.get(f"/api/echo/referrals/{first['id']}/matches")).json()["matches"][0][
        "specialist"
    ]["id"]
    slot = (await c.get(f"/api/echo/specialists/{sp}/slots")).json()[0]
    body = {"specialistId": sp, "slotId": slot["id"]}
    assert (
        await c.post(f"/api/echo/referrals/{first['id']}/approve", json=body)
    ).status_code == 200
    taken = await c.post(f"/api/echo/referrals/{second['id']}/approve", json=body)
    assert taken.status_code == 409
    after = (await c.get(f"/api/echo/referrals/{second['id']}")).json()
    assert after["status"] == "awaiting_approval" and after["appointmentAt"] is None


async def test_cannot_approve_a_specialist_outside_the_results(echo):
    c = echo.client
    ref = await _create(echo)
    r = await c.post(
        f"/api/echo/referrals/{ref['id']}/approve", json={"specialistId": "sp_meyer", "slotId": "x"}
    )
    assert r.status_code in (409, 422)
    assert (await c.get(f"/api/echo/referrals/{ref['id']}")).json()["status"] == "awaiting_approval"


async def test_only_the_referring_physician_sees_and_approves(echo):
    ref = await _create(echo)
    other = echo.as_physician("doc_002")
    assert (await other.get(f"/api/echo/referrals/{ref['id']}")).status_code == 404
    assert ref["id"] not in {r["id"] for r in (await other.get("/api/echo/referrals")).json()}
    echo.as_physician("doc_001")


# ---- analysis failure and retry --------------------------------------------------------------------


async def test_a_failed_run_reports_error_and_retry_recovers(echo):
    class Broken:
        async def candidates_for(self, patient, specialists):
            raise RuntimeError("provider down")

    good = echo.state["provider"]
    echo.state["provider"] = Broken()
    ref = await _create(echo)
    c = echo.client
    snap = (await c.get(f"/api/echo/referrals/{ref['id']}/analysis")).json()
    assert snap["status"] == "error" and snap["matchCount"] is None
    assert [k["state"] for k in snap["checks"]].count("error") == 1
    assert (await c.get(f"/api/echo/referrals/{ref['id']}/matches")).status_code == 409
    listed = next(r for r in (await c.get("/api/echo/referrals")).json() if r["id"] == ref["id"])
    assert listed["attention"]["action"] == "Retry analysis"

    echo.state["provider"] = good
    retried = (await c.post(f"/api/echo/referrals/{ref['id']}/analysis/retry")).json()
    assert retried["status"] in {"running", "complete"}
    snap = (await c.get(f"/api/echo/referrals/{ref['id']}/analysis")).json()
    assert snap["status"] == "complete" and snap["matchCount"] >= 1


# ---- tracking and the patient's answer ------------------------------------------------------------


async def test_patient_response_is_dev_only_and_shows_in_tracking(echo):
    c = echo.client
    ref = await _create(echo)
    rid = ref["id"]
    assert (
        await c.post(f"/api/echo/referrals/{rid}/patient-response", json={"status": "confirmed"})
    ).status_code == 409
    sp = (await c.get(f"/api/echo/referrals/{rid}/matches")).json()["matches"][0]["specialist"][
        "id"
    ]
    slot = (await c.get(f"/api/echo/specialists/{sp}/slots")).json()[0]
    await c.post(
        f"/api/echo/referrals/{rid}/approve", json={"specialistId": sp, "slotId": slot["id"]}
    )
    done = (
        await c.post(f"/api/echo/referrals/{rid}/patient-response", json={"status": "declined"})
    ).json()
    assert done["patientConfirmation"]["status"] == "declined"
    assert done["patientConfirmation"]["respondedAt"]
    assert done["timeline"][-1]["kind"] == "patient_declined"


# ---- consult (chat) --------------------------------------------------------------------------------


async def _start(
    c, colleague="doc_002", text="MRI first, or refer directly to knee surgery?", referral=None
):
    body = {
        "colleagueId": colleague,
        "text": text,
        **({"referralId": referral} if referral else {}),
    }
    return await c.post("/api/echo/consults", json=body)


async def test_consult_is_a_chat_with_many_messages_and_no_referral_needed(echo):
    c = echo.client
    assert (await c.get("/api/echo/consults")).json() == []

    started = await _start(c)  # no referral: a physician can consult a colleague any time
    assert started.status_code == 201, started.text
    t = started.json()
    assert t["referral"] is None and t["sharedContext"] is None
    assert t["colleague"]["id"] == "doc_002" and t["status"] == "pending"
    assert [m["text"] for m in t["messages"]] == ["MRI first, or refer directly to knee surgery?"]
    assert t["messages"][0]["fromMe"] is True and t["lastMessage"]["fromMe"] is True

    # The colleague answers through the core consult API; then I follow up.
    echo.as_physician("doc_002")
    r = await c.post(
        f"/consults/{t['id']}/messages",
        json={"sender_physician_id": "doc_002", "body": "MRI first."},
    )
    assert r.status_code == 201
    echo.as_physician("doc_001")
    got = (await c.get(f"/api/echo/consults/{t['id']}")).json()
    assert got["status"] == "responded" and got["lastMessage"] == {
        **got["lastMessage"],
        "text": "MRI first.",
        "fromMe": False,
    }
    followup = await c.post(
        f"/api/echo/consults/{t['id']}/messages", json={"text": "  Thanks. Before the visit?  "}
    )
    assert followup.status_code == 201
    got = followup.json()
    assert [(m["fromMe"], m["text"]) for m in got["messages"]] == [
        (True, "MRI first, or refer directly to knee surgery?"),
        (False, "MRI first."),
        (True, "Thanks. Before the visit?"),
    ]
    assert got["status"] == "pending"  # my message is last: waiting for a response again

    listed = (await c.get("/api/echo/consults")).json()
    assert [x["id"] for x in listed] == [t["id"]]
    assert set(listed[0]) == {
        "id",
        "colleague",
        "referral",
        "status",
        "lastMessage",
    }  # no messages in the list


async def test_consult_about_a_referral_shows_the_sender_the_patient_but_never_the_colleague(echo):
    c = echo.client
    ref = await _create(echo)
    t = (await _start(c, referral=ref["id"])).json()
    assert t["referral"] == {
        "id": ref["id"],
        "patientName": "Maria Lopez",
        "age": 58,
        "sex": "F",
        "reason": KNEE_FORM["reason"],
    }
    ctx = t["sharedContext"]
    assert set(ctx) == {"age", "sex", "reason", "summary"} and "Lopez" not in str(ctx)

    echo.as_physician("doc_002")  # the colleague's view of the same conversation
    theirs = (await c.get(f"/api/echo/consults/{t['id']}")).json()
    assert theirs["colleague"]["id"] == "doc_001"  # "the other person" is the sender
    assert theirs["referral"] is None  # they never see the referral or the patient's name
    assert "Lopez" not in str(theirs) and theirs["sharedContext"]["age"] == 58
    assert theirs["status"] == "responded"  # their turn: the last message is not theirs
    assert [x["id"] for x in (await c.get("/api/echo/consults")).json()] == [t["id"]]
    echo.as_physician("doc_001")


async def test_consult_validation_and_privacy(echo):
    c = echo.client
    ref = await _create(echo)
    assert (await _start(c, colleague="doc_001")).status_code == 422  # not yourself
    assert (await _start(c, colleague="nope")).status_code == 404
    assert (await _start(c, text="")).status_code == 422
    assert (await _start(c, text="   ")).status_code == 422
    assert (await _start(c, referral="nope")).status_code == 404
    echo.as_physician("doc_003")  # someone else's referral can't be attached
    assert (await _start(c, referral=ref["id"])).status_code == 404
    echo.as_physician("doc_001")
    assert (await c.get("/api/echo/consults")).json() == []  # nothing was created by the failures

    t = (await _start(c)).json()
    echo.as_physician("doc_003")  # a stranger sees nothing of it
    assert (await c.get(f"/api/echo/consults/{t['id']}")).status_code == 404
    assert (
        await c.post(f"/api/echo/consults/{t['id']}/messages", json={"text": "hi"})
    ).status_code == 404
    assert (await c.get("/api/echo/consults")).json() == []
    echo.as_physician("doc_001")
    assert (
        await c.post(f"/api/echo/consults/{t['id']}/messages", json={"text": " "})
    ).status_code == 422
    assert (await c.get("/api/echo/consults/nope")).status_code == 404


async def test_conversations_are_newest_activity_first(echo):
    c = echo.client
    a = (await _start(c, colleague="doc_002", text="first")).json()
    b = (await _start(c, colleague="doc_003", text="second")).json()
    assert [x["id"] for x in (await c.get("/api/echo/consults")).json()] == [b["id"], a["id"]]
    await c.post(
        f"/api/echo/consults/{a['id']}/messages", json={"text": "bump"}
    )  # activity on the older one
    assert [x["id"] for x in (await c.get("/api/echo/consults")).json()] == [a["id"], b["id"]]


# ---- clinical trials -------------------------------------------------------------------------------


async def test_trials_criteria_results_and_widening(echo):
    c = echo.client
    ref = await _create(echo, RARE_FORM)
    rid = ref["id"]
    crit = (await c.get(f"/api/echo/referrals/{rid}/trials/criteria")).json()
    assert crit == {
        "condition": RARE_FORM["reason"],
        "patient": "67y M",
        "location": "Within 100 miles of Cambridge, MA",
        "status": "Recruiting or not yet recruiting",
        "source": "ClinicalTrials.gov",
        "distanceMiles": 100,
        "allStatuses": False,
    }
    res = (await c.get(f"/api/echo/referrals/{rid}/trials")).json()
    assert res["referralId"] == rid and len(res["trials"]) >= 1
    t = res["trials"][0]
    assert set(t) == {
        "nctId", "title", "condition", "intervention", "location",
        "distanceMiles", "status", "relevance", "url",
    }  # fmt: skip
    assert t["url"] == f"https://clinicaltrials.gov/study/{t['nctId']}"
    assert t["status"] in {"recruiting", "not_yet_recruiting"}
    assert not {"score", "eligible", "eligibility"} & set(t)
    dists = [x["distanceMiles"] for x in res["trials"]]
    assert dists == sorted(dists)  # nearest first

    # The widen actions: any location and all statuses are separate, explicit searches.
    any_loc = (await c.get(f"/api/echo/referrals/{rid}/trials/criteria?distanceMiles=any")).json()
    assert any_loc["location"] == "Any location" and any_loc["distanceMiles"] is None
    tight = (await c.get(f"/api/echo/referrals/{rid}/trials?distanceMiles=1")).json()
    assert tight["trials"] == []
    assert (await c.get(f"/api/echo/referrals/{rid}/trials?distanceMiles=abc")).status_code == 422


async def test_trials_all_statuses_includes_not_recruiting(echo):
    c = echo.client
    ref = await _create(
        echo,
        {
            **RARE_FORM,
            "reason": "Numbness and tremor",
            "details": "Neuropathy: numbness and tremor of unclear cause.",
        },
    )
    rid = ref["id"]
    default = (await c.get(f"/api/echo/referrals/{rid}/trials?distanceMiles=any")).json()["trials"]
    everything = (
        await c.get(f"/api/echo/referrals/{rid}/trials?distanceMiles=any&allStatuses=true")
    ).json()["trials"]
    assert "active_not_recruiting" not in {t["status"] for t in default}
    assert "active_not_recruiting" in {t["status"] for t in everything}


async def test_no_matching_trials_is_an_empty_result_not_an_error(echo):
    ref = await _create(echo)  # knee: the synthetic trial list has nothing for it
    r = await echo.client.get(f"/api/echo/referrals/{ref['id']}/trials")
    assert r.status_code == 200 and r.json()["trials"] == []


# ---- referrals created outside /api/echo ---------------------------------------------------------


async def test_core_demo_referrals_are_described_without_form_data(echo):
    c = echo.client
    refs = (await c.get("/api/echo/referrals")).json()
    demo = next(r for r in refs if r["id"] == "ref_demo_knee")
    assert demo["status"] == "awaiting_approval" and demo["reason"] and demo["details"]
    assert demo["patient"]["name"] and demo["timeline"][0]["kind"] == "created"
    # The frontend can start the analysis for one of them through the retry endpoint.
    snap = (await c.get("/api/echo/referrals/ref_demo_knee/analysis")).json()
    assert snap["status"] == "error"  # never analyzed: nothing is running
    retried = (await c.post("/api/echo/referrals/ref_demo_knee/analysis/retry")).json()
    assert retried["status"] in {"running", "complete"}
    assert (await c.get("/api/echo/referrals/ref_demo_knee/analysis")).json()[
        "status"
    ] == "complete"


# ---- authentication ---------------------------------------------------------------------------------


async def test_dev_mode_defaults_to_the_configured_physician_without_a_header(echo, monkeypatch):
    del echo.client.headers["X-Dev-Physician"]  # the browser frontend sends none
    assert (await echo.client.get("/api/echo/me")).json()["id"] == "doc_001"
    monkeypatch.setattr(settings, "dev_default_physician", "doc_003")
    assert (await echo.client.get("/api/echo/me")).json()["id"] == "doc_003"
    monkeypatch.setattr(settings, "dev_default_physician", None)
    assert (await echo.client.get("/api/echo/me")).status_code == 401  # header required again
    assert (await echo.client.get("/api/echo/me", headers={"X-Dev-Physician": "doc_002"})).json()[
        "id"
    ] == "doc_002"


async def test_auth0_mode_never_falls_back_to_a_default(echo, monkeypatch):
    monkeypatch.setattr(settings, "auth_mode", "auth0")
    monkeypatch.setattr(settings, "auth0_domain", "echo-test.us.auth0.com")
    monkeypatch.setattr(settings, "auth0_audience", "https://api.echo.test")
    del echo.client.headers["X-Dev-Physician"]
    assert (await echo.client.get("/api/echo/me")).status_code == 401
    assert (
        await echo.client.get("/api/echo/me", headers={"X-Dev-Physician": "doc_001"})
    ).status_code == 401
    # and the dev-only endpoint disappears
    assert (
        await echo.client.post(
            "/api/echo/referrals/x/patient-response", json={"status": "confirmed"}
        )
    ).status_code in (401, 404)


# ---- the form's specialty reaches the matcher --------------------------------------------------------


async def test_form_specialty_is_used_when_the_keywords_miss(echo):
    """ "Skin burns, redness" has none of the fallback's dermatology words; the physician still
    chose Dermatology, so the specialist must still be found."""
    form = {
        **KNEE_FORM,
        "specialty": "Dermatology",
        "subspecialty": "Medical dermatology",
        "reason": "Skin burns",
        "details": "Redness and blistering after sun exposure.",
    }
    ref = await _create(echo, form)
    res = (await echo.client.get(f"/api/echo/referrals/{ref['id']}/matches")).json()
    assert [m["specialist"]["name"] for m in res["matches"]] == ["Dr. Ngozi Okafor"]
    # Added to what the parser found, and said so.
    async with echo.factory() as session:
        from app.db.repository import Repository

        parsed = (await Repository(session).referral(ref["id"])).parsed_case
    assert "Dermatology" in parsed.suggested_specialties
    assert "Added from the referral form" in parsed.rationale


async def test_retry_reapplies_the_form_specialty_to_an_already_analyzed_referral(echo):
    """A referral analyzed before the hint existed (0 matches) is fixed by retrying its analysis."""
    form = {**KNEE_FORM, "specialty": "Dermatology", "subspecialty": None,
            "reason": "Skin burns", "details": "Redness and blistering."}  # fmt: skip
    ref = await _create(echo, form)
    async with echo.factory() as session:  # undo the hint, as the older code left it
        from app.db.repository import Repository

        repo = Repository(session)
        r = await repo.referral(ref["id"])
        r.parsed_case = r.parsed_case.model_copy(update={"suggested_specialties": []})
        await repo.save_referral(r)
    c = echo.client
    retried = (await c.post(f"/api/echo/referrals/{ref['id']}/analysis/retry")).json()
    assert retried["status"] in {"running", "complete"}
    # No subspecialty was chosen, so the fit is partial: found, but listed under "show partial".
    found = (await c.get(f"/api/echo/referrals/{ref['id']}/matches?includePartial=true")).json()
    assert [m["strength"] for m in found["matches"]] == ["partial"]


# ---- "nobody found" must not be the answer while the ranking found people --------------------------


async def test_every_seeded_patient_gets_someone_in_every_specialty(echo):
    """Regression: the default list used to require every factor (distance, insurance, fit), which
    left ~69% of seeded patient/specialty combinations with an empty page."""
    c = echo.client
    options = (await c.get("/api/echo/referral-options")).json()
    for urgency in ("routine", "urgent"):
        for patient in (await c.get("/api/echo/patients")).json():
            for spec in options["specialties"]:
                form = {
                    **KNEE_FORM,
                    "patientId": patient["id"],
                    "insurance": patient["insurance"],
                    "specialty": spec["name"],
                    "subspecialty": spec["subspecialties"][0],
                    "urgency": urgency,
                    "reason": "Evaluation requested",
                    "details": "Patient needs a specialist evaluation.",
                }
                rid = (await c.post("/api/echo/referrals", json=form)).json()["id"]
                res = (await c.get(f"/api/echo/referrals/{rid}/matches")).json()
                where = (urgency, patient["name"], spec["name"])
                assert res["matches"], f"nobody shown for {where}: {res['noMatchReason']}"
                assert res["noMatchReason"] is None


async def test_partial_matches_are_labelled_and_show_what_they_miss(echo):
    ref = await _create(echo, {**KNEE_FORM, "patientId": "pat_004", "insurance": "Medicare"})
    res = (await echo.client.get(f"/api/echo/referrals/{ref['id']}/matches")).json()
    partial = [m for m in res["matches"] if m["strength"] == "partial"]
    for m in partial:  # a partial match is never presented as a good one
        assert any(f["status"] != "met" for f in m["factors"])
        assert all(f["detail"] for f in m["factors"])
    # And a strong/good match is never mixed in behind them unless it exists.
    strengths = [m["strength"] for m in res["matches"]]
    assert strengths == sorted(strengths, key=lambda x: x == "partial")


async def test_opening_matches_analyzes_a_referral_nobody_analyzed(echo):
    """The seeded demo referrals were never analyzed; 'Review matches' used to end in a 409."""
    c = echo.client
    assert (await c.get("/api/echo/referrals/ref_demo_knee/analysis")).json()["status"] == "error"
    res = await c.get("/api/echo/referrals/ref_demo_knee/matches")
    assert res.status_code == 200, res.text
    assert res.json()["matches"], res.json()
    assert (await c.get("/api/echo/referrals/ref_demo_knee/analysis")).json()[
        "status"
    ] == "complete"
    again = await c.get("/api/echo/referrals/ref_demo_knee/matches")  # not analyzed a second time
    assert again.json() == res.json()
