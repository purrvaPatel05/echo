from datetime import date

import pytest

from app.matching import config
from app.matching.ranking import rank_candidates
from app.matching.scoring import select_weight_profile
from app.matching.types import Candidate
from app.models.enums import (
    Complexity,
    FactorName,
    FitTier,
    InsuranceStatus,
    Urgency,
    Verdict,
    WeightProfile,
)
from app.models.match import ClinicalFit, InsuranceCheck
from app.models.people import Patient, Specialist
from app.seed.data import PATIENTS, SPECIALISTS
from app.seed.fixtures import FixtureCandidateProvider
from tests.scenarios import SCENARIOS

TODAY = date(2026, 9, 21)
PATIENT_BY_ID = {p.id: p for p in PATIENTS}


async def _candidates(patient: Patient, specialists: list[Specialist] = SPECIALISTS):
    return await FixtureCandidateProvider(today=TODAY).candidates_for(patient, specialists)


def _fits(tiers: dict[str, FitTier]) -> dict[str, ClinicalFit]:
    return {k: ClinicalFit(tier=t, rationale=f"scripted {t.value}") for k, t in tiers.items()}


@pytest.mark.parametrize("scenario", SCENARIOS, ids=lambda s: s.id)
async def test_demo_scenarios(scenario):
    candidates = await _candidates(PATIENT_BY_ID[scenario.patient_id])
    outcome = rank_candidates(
        candidates, _fits(scenario.fits), scenario.urgency, scenario.complexity
    )
    assert [r.specialist.id for r in outcome.results] == scenario.expected_order
    assert [t.specialist.id for t in outcome.too_late] == scenario.expected_too_late
    assert outcome.weight_profile == scenario.expected_profile
    assert [r.rank for r in outcome.results] == list(range(1, len(outcome.results) + 1))
    assert outcome.results[0].why_not_first is None
    for r in outcome.results:
        assert 0 <= r.match_percent <= 100
        assert sum(f.weight for f in r.factors) == pytest.approx(1.0)


async def test_out_of_network_expert_carries_warning_and_tradeoff_note():
    scenario = next(s for s in SCENARIOS if s.id.startswith("out_of_network"))
    candidates = await _candidates(PATIENT_BY_ID[scenario.patient_id])
    top, second = rank_candidates(
        candidates, _fits(scenario.fits), scenario.urgency, scenario.complexity
    ).results
    insurance = next(f for f in top.factors if f.factor == FactorName.INSURANCE)
    assert insurance.verdict == Verdict.CAUTION
    assert top.insurance.status == InsuranceStatus.OUT_OF_NETWORK
    assert second.why_not_first == "Closer, sooner and better coverage, but weaker clinical fit"


async def test_clinical_fit_reported_separately_from_match_percent():
    scenario = SCENARIOS[0]
    candidates = await _candidates(PATIENT_BY_ID[scenario.patient_id])
    top = rank_candidates(
        candidates, _fits(scenario.fits), scenario.urgency, scenario.complexity
    ).results[0]
    assert top.clinical_fit.tier == FitTier.EXCELLENT
    assert top.factors[0].factor == FactorName.CLINICAL_FIT
    assert "miles away" in top.explanation


def _candidate(sp_id, miles=10.0, days=5, status=InsuranceStatus.IN_NETWORK) -> Candidate:
    base = next(s for s in SPECIALISTS if s.id == "sp_chen")
    return Candidate(
        specialist=base.model_copy(update={"id": sp_id}),
        distance_miles=miles,
        insurance=InsuranceCheck(status=status, detail="test"),
        days_until_slot=days,
    )


def test_missing_fit_assessment_is_gated_out():
    outcome = rank_candidates(
        [_candidate("a"), _candidate("b")],
        _fits({"a": FitTier.GOOD}),  # b was never assessed
        Urgency.ROUTINE,
        Complexity.ROUTINE,
    )
    assert [r.specialist.id for r in outcome.results] == ["a"]
    assert outcome.too_late == []


def test_no_open_appointments_is_listed_as_too_late():
    c = _candidate("a")
    c.days_until_slot = None
    outcome = rank_candidates(
        [c], _fits({"a": FitTier.EXCELLENT}), Urgency.ROUTINE, Complexity.ROUTINE
    )
    assert outcome.results == []
    assert outcome.too_late[0].detail == "No open appointments"


def test_gated_candidates_are_never_listed_as_too_late():
    late_but_poor = _candidate("a", days=99)
    late_but_unaccepted = _candidate("b", days=99, status=InsuranceStatus.NOT_ACCEPTED)
    outcome = rank_candidates(
        [late_but_poor, late_but_unaccepted],
        _fits({"a": FitTier.POOR, "b": FitTier.EXCELLENT}),
        Urgency.ROUTINE,
        Complexity.ROUTINE,
    )
    assert outcome.results == [] and outcome.too_late == []


def test_ties_break_on_earlier_appointment():
    # Equal totals under routine weights: (dist 1.0, avail 0.5) vs (dist 1/3, avail 1.0).
    far_soon = _candidate("far_soon", miles=35.0, days=0)
    near_later = _candidate("near_later", miles=5.0, days=30)
    outcome = rank_candidates(
        [near_later, far_soon],
        _fits({"far_soon": FitTier.EXCELLENT, "near_later": FitTier.EXCELLENT}),
        Urgency.ROUTINE,
        Complexity.ROUTINE,
    )
    assert [r.specialist.id for r in outcome.results] == ["far_soon", "near_later"]


def test_convenience_cannot_buy_back_clinical_fit_under_rare_profile():
    perfect_logistics_weak_fit = _candidate("weak", miles=1.0, days=0)
    strong_fit_worse_logistics = _candidate("strong", miles=40.0, days=30)
    outcome = rank_candidates(
        [perfect_logistics_weak_fit, strong_fit_worse_logistics],
        _fits({"weak": FitTier.PARTIAL, "strong": FitTier.EXCELLENT}),
        Urgency.ROUTINE,
        Complexity.RARE_COMPLEX,
    )
    assert outcome.results[0].specialist.id == "strong"


@pytest.mark.parametrize(
    ("urgency", "complexity", "expected"),
    [
        (Urgency.ROUTINE, Complexity.ROUTINE, WeightProfile.ROUTINE),
        (Urgency.SOON, Complexity.ROUTINE, WeightProfile.ROUTINE),
        (Urgency.URGENT, Complexity.ROUTINE, WeightProfile.URGENT),
        (Urgency.ROUTINE, Complexity.RARE_COMPLEX, WeightProfile.RARE_COMPLEX),
        (Urgency.URGENT, Complexity.RARE_COMPLEX, WeightProfile.URGENT_RARE_COMPLEX),
    ],
)
def test_weight_profile_selection(urgency, complexity, expected):
    assert select_weight_profile(urgency, complexity) == expected


def test_urgent_rare_profile_is_the_average_and_sums_to_one():
    blend = config.WEIGHT_PROFILES[WeightProfile.URGENT_RARE_COMPLEX]
    assert blend[FactorName.CLINICAL_FIT] == pytest.approx(0.525)
    assert blend[FactorName.AVAILABILITY] == pytest.approx(0.225)
    assert blend[FactorName.INSURANCE] == pytest.approx(0.10)
    assert blend[FactorName.DISTANCE] == pytest.approx(0.15)
    assert sum(blend.values()) == pytest.approx(1.0)


def test_results_are_capped_and_keep_the_best_matches():
    candidates = [_candidate(f"sp_{i}", miles=5.0 + 5 * i, days=1) for i in range(8)]
    fits = _fits({f"sp_{i}": FitTier.EXCELLENT for i in range(8)})
    outcome = rank_candidates(candidates, fits, Urgency.ROUTINE, Complexity.ROUTINE)
    assert len(outcome.results) == config.MAX_RESULTS == 5
    # nearest five win; the three farthest are the ones dropped
    assert [r.specialist.id for r in outcome.results] == [f"sp_{i}" for i in range(5)]
    assert [r.rank for r in outcome.results] == [1, 2, 3, 4, 5]
