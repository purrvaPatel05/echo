"""Gate -> score -> rank -> explain. Pure and deterministic; no I/O, no Claude."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.matching.config import MAX_RESULTS, VERDICT_GOOD_MIN_SCORE, WEIGHT_PROFILES
from app.matching.scoring import (
    availability_score,
    distance_score,
    fit_score,
    insurance_score,
    select_weight_profile,
    within_urgency_window,
)
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
from app.models.match import (
    ClinicalFit,
    FactorResult,
    MatchResult,
    TooLateCandidate,
)

_NOT_ASSESSED = ClinicalFit(tier=FitTier.POOR, rationale="Not assessed")


@dataclass
class RankOutcome:
    results: list[MatchResult]
    too_late: list[TooLateCandidate]
    weight_profile: WeightProfile


def _verdict(score: float) -> Verdict:
    return Verdict.GOOD if score >= VERDICT_GOOD_MIN_SCORE else Verdict.CAUTION


def _insurance_verdict(status: InsuranceStatus) -> Verdict:
    if status == InsuranceStatus.IN_NETWORK:
        return Verdict.GOOD
    if status == InsuranceStatus.UNVERIFIED:
        return Verdict.UNKNOWN
    return Verdict.CAUTION


def _appointment_phrase(days: int) -> str:
    if days <= 0:
        return "Appointment available today"
    return f"Appointment available in {days} day{'s' if days != 1 else ''}"


@dataclass
class _Scored:
    candidate: Candidate
    fit: ClinicalFit
    days: int
    fit_s: float
    ins_s: float
    dist_s: float
    avail_s: float
    total: float
    result: MatchResult | None = None


def _score(
    c: Candidate,
    fit: ClinicalFit,
    days: int,
    urgency: Urgency,
    weights: Mapping[FactorName, float],
) -> _Scored:
    fit_s = fit_score(fit.tier)
    ins_s = insurance_score(c.insurance.status)
    assert fit_s is not None and ins_s is not None  # gated candidates never reach scoring
    dist_s = distance_score(c.distance_miles)
    avail_s = availability_score(days, urgency)
    total = (
        weights[FactorName.CLINICAL_FIT] * fit_s
        + weights[FactorName.AVAILABILITY] * avail_s
        + weights[FactorName.INSURANCE] * ins_s
        + weights[FactorName.DISTANCE] * dist_s
    )
    return _Scored(c, fit, days, fit_s, ins_s, dist_s, avail_s, total)


def _factors(s: _Scored, weights: Mapping[FactorName, float]) -> list[FactorResult]:
    c = s.candidate
    return [
        FactorResult(
            factor=FactorName.CLINICAL_FIT,
            verdict=_verdict(s.fit_s),
            score=s.fit_s,
            weight=weights[FactorName.CLINICAL_FIT],
            detail=f"{s.fit.tier.value.capitalize()} clinical fit",
        ),
        FactorResult(
            factor=FactorName.INSURANCE,
            verdict=_insurance_verdict(c.insurance.status),
            score=s.ins_s,
            weight=weights[FactorName.INSURANCE],
            detail=c.insurance.detail,
        ),
        FactorResult(
            factor=FactorName.DISTANCE,
            verdict=_verdict(s.dist_s),
            score=s.dist_s,
            weight=weights[FactorName.DISTANCE],
            detail=f"{c.distance_miles:.1f} miles away",
        ),
        FactorResult(
            factor=FactorName.AVAILABILITY,
            verdict=_verdict(s.avail_s),
            score=s.avail_s,
            weight=weights[FactorName.AVAILABILITY],
            detail=_appointment_phrase(s.days),
        ),
    ]


def _explanation(s: _Scored) -> str:
    c = s.candidate
    return (
        f"{s.fit.tier.value.capitalize()} clinical fit: {s.fit.rationale.rstrip('.')}. "
        f"{c.insurance.detail}; {c.distance_miles:.1f} miles away; "
        f"{_appointment_phrase(s.days).lower()}."
    )


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def _why_not_first(s: _Scored, top: _Scored) -> str:
    """Say how this specialist differs from #1, so the physician sees the tradeoff."""
    better, worse = [], []
    for label_better, label_worse, mine, theirs in (
        ("closer", "farther away", top.candidate.distance_miles, s.candidate.distance_miles),
        ("sooner", "later appointment", top.days, s.days),
    ):
        if theirs < mine:
            better.append(label_better)
        elif theirs > mine:
            worse.append(label_worse)
    if s.ins_s > top.ins_s:
        better.append("better coverage")
    elif s.ins_s < top.ins_s:
        worse.append("less favorable coverage")
    if s.fit_s > top.fit_s:
        better.append("stronger clinical fit")
    elif s.fit_s < top.fit_s:
        worse.append("weaker clinical fit")
    if better and worse:
        text = f"{_join(better)}, but {_join(worse)}"
        return text[0].upper() + text[1:]
    if worse:
        return f"Lower overall match: {_join(worse)}"
    return "Comparable match; ranked just below"


def rank_candidates(
    candidates: Sequence[Candidate],
    fits: Mapping[str, ClinicalFit],
    urgency: Urgency,
    complexity: Complexity,
) -> RankOutcome:
    profile = select_weight_profile(urgency, complexity)
    weights = WEIGHT_PROFILES[profile]

    scored: list[_Scored] = []
    too_late: list[TooLateCandidate] = []
    for c in candidates:
        fit = fits.get(c.specialist.id, _NOT_ASSESSED)
        # Gates. Poor fit and unaccepted insurance are dropped silently: they never appear.
        if fit_score(fit.tier) is None or insurance_score(c.insurance.status) is None:
            continue
        if c.days_until_slot is None or not within_urgency_window(c.days_until_slot, urgency):
            detail = (
                "No open appointments"
                if c.days_until_slot is None
                else f"Earliest appointment is in {c.days_until_slot} days, "
                f"outside the {urgency.value} window"
            )
            too_late.append(
                TooLateCandidate(
                    specialist=c.specialist, earliest_slot=c.earliest_slot, detail=detail
                )
            )
            continue
        scored.append(_score(c, fit, c.days_until_slot, urgency, weights))

    # Ties (after rounding away float noise) break on earlier appointment, then shorter distance.
    scored.sort(key=lambda s: (-round(s.total, 9), s.days, s.candidate.distance_miles))
    scored = scored[:MAX_RESULTS]

    results = []
    for rank, s in enumerate(scored, start=1):
        c = s.candidate
        results.append(
            MatchResult(
                rank=rank,
                specialist=c.specialist,
                match_percent=round(s.total * 100),
                clinical_fit=s.fit,
                insurance=c.insurance,
                distance_miles=c.distance_miles,
                earliest_slot=c.earliest_slot,
                days_until_slot=s.days,
                factors=_factors(s, weights),
                explanation=_explanation(s),
                why_not_first=None if rank == 1 else _why_not_first(s, scored[0]),
            )
        )
    return RankOutcome(results=results, too_late=too_late, weight_profile=profile)
