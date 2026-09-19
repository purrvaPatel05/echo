"""ClinicalTrials.gov (mocked): the keyword matcher, the rare_complex gate, and the
physician-approval gate before a trial reaches the patient summary."""

from app.matching.rules_analyzer import RulesAnalyzer
from app.models.enums import Urgency
from app.trials.data import TRIALS
from app.trials.matcher import match_trials

KNEE, RARE_NEURO, RARE_PULM = "ref_demo_knee", "ref_demo_rare_neuro", "ref_demo_rare_pulm"
KNEE_DOC, NEURO_DOC, PULM_DOC = "doc_001", "doc_002", "doc_003"

_CASES = {
    "knee": "58F, 3 months progressive right knee pain, worse on stairs. Swelling after "
    "activity. No trauma. X-ray shows joint space narrowing.",
    "rare_neuro": "34M with progressive proximal muscle weakness over 8 months and persistently "
    "elevated CK. Initial workup nondiagnostic. Family history of an undiagnosed neuromuscular "
    "disorder. Suspect a rare inherited or inflammatory myopathy.",
    "rare_pulm": "67M with refractory pulmonary arterial hypertension despite standard therapy, "
    "worsening dyspnea and exercise intolerance. Considering advanced or investigational "
    "options.",
}


# ---- pure matcher ------------------------------------------------------------------------------


async def test_matcher_finds_relevant_trial_for_rare_neuro_case():
    parsed = await RulesAnalyzer().parse_case(_CASES["rare_neuro"], Urgency.ROUTINE)
    matches = match_trials(parsed)
    assert [t.id for t in matches] == ["trial_myopathy_01"]


async def test_matcher_finds_relevant_trial_for_rare_pulm_case():
    parsed = await RulesAnalyzer().parse_case(_CASES["rare_pulm"], Urgency.ROUTINE)
    matches = match_trials(parsed)
    assert [t.id for t in matches] == ["trial_pah_01"]


async def test_matcher_finds_nothing_for_unrelated_case():
    parsed = await RulesAnalyzer().parse_case(_CASES["knee"], Urgency.ROUTINE)
    assert match_trials(parsed) == []


def test_all_trials_have_distinct_ids():
    ids = [t.id for t in TRIALS]
    assert len(ids) == len(set(ids))


# ---- router/service, via the `api` fixture ------------------------------------------------------


async def test_trials_endpoint_gates_on_parsed_and_rare_complex(api):
    c = api.client
    assert (await c.get(f"/referrals/{KNEE}/trials")).status_code == 409  # not parsed yet

    await c.post(f"/referrals/{KNEE}/parse")
    await c.patch(f"/referrals/{KNEE}", json={"complexity": "routine"})
    r = await c.get(f"/referrals/{KNEE}/trials")
    assert r.status_code == 409  # routine, not rare_complex


async def test_trials_endpoint_lists_matches_for_rare_complex_referral(api):
    c = api.client
    await c.post(f"/referrals/{RARE_NEURO}/parse")
    await c.patch(f"/referrals/{RARE_NEURO}", json={"complexity": "rare_complex"})
    r = await c.get(f"/referrals/{RARE_NEURO}/trials")
    assert r.status_code == 200
    assert [t["id"] for t in r.json()] == ["trial_myopathy_01"]


async def test_approve_trial_requires_referring_physician(api):
    c = api.client
    await c.post(f"/referrals/{RARE_NEURO}/parse")
    await c.patch(f"/referrals/{RARE_NEURO}", json={"complexity": "rare_complex"})
    r = await c.post(
        f"/referrals/{RARE_NEURO}/trials/trial_myopathy_01/approve",
        json={"approved_by": "doc_999"},
    )
    assert r.status_code == 403


async def test_approve_trial_rejects_unmatched_trial(api):
    c = api.client
    await c.post(f"/referrals/{RARE_NEURO}/parse")
    await c.patch(f"/referrals/{RARE_NEURO}", json={"complexity": "rare_complex"})
    r = await c.post(
        f"/referrals/{RARE_NEURO}/trials/trial_pah_01/approve",  # not matched for this case
        json={"approved_by": NEURO_DOC},
    )
    assert r.status_code == 422


async def test_approved_trial_only_reaches_patient_summary_after_specialist_approval(api):
    c = api.client
    await c.post(f"/referrals/{RARE_PULM}/parse")
    await c.patch(f"/referrals/{RARE_PULM}", json={"complexity": "rare_complex"})

    approve_trial = await c.post(
        f"/referrals/{RARE_PULM}/trials/trial_pah_01/approve", json={"approved_by": PULM_DOC}
    )
    assert approve_trial.status_code == 200
    assert approve_trial.json()["trial_approval"]["trial_id"] == "trial_pah_01"

    # approved, but no specialist approval yet: patient summary stays generic
    summary = (await c.get(f"/referrals/{RARE_PULM}/patient-summary")).json()
    assert summary["trial_note"] is None

    run = (await c.post(f"/referrals/{RARE_PULM}/match")).json()
    run = (await c.get(f"/referrals/{RARE_PULM}/match")).json()
    top = run["results"][0]
    await c.post(
        f"/referrals/{RARE_PULM}/approve",
        json={
            "match_run_id": run["id"],
            "specialist_id": top["specialist"]["id"],
            "slot_id": top["earliest_slot"]["id"],
            "approved_by": PULM_DOC,
        },
    )

    summary = (await c.get(f"/referrals/{RARE_PULM}/patient-summary")).json()
    assert "Novel Add-On Therapy" in summary["trial_note"]
