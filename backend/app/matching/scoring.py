"""Deterministic sub-scores (each 0-1). Pure functions: no I/O, no Claude."""

from app.matching.config import (
    DISTANCE_FULL_MILES,
    DISTANCE_ZERO_MILES,
    FIT_TIER_SCORE,
    INSURANCE_SCORE,
    URGENCY_WINDOW_DAYS,
)
from app.models.enums import Complexity, FitTier, InsuranceStatus, Urgency, WeightProfile


def fit_score(tier: FitTier) -> float | None:
    """None means gated out (POOR)."""
    return FIT_TIER_SCORE.get(tier)


def insurance_score(status: InsuranceStatus) -> float | None:
    """None means gated out (NOT_ACCEPTED)."""
    return INSURANCE_SCORE.get(status)


def distance_score(miles: float) -> float:
    if miles <= DISTANCE_FULL_MILES:
        return 1.0
    if miles >= DISTANCE_ZERO_MILES:
        return 0.0
    return (DISTANCE_ZERO_MILES - miles) / (DISTANCE_ZERO_MILES - DISTANCE_FULL_MILES)


def within_urgency_window(days_until_slot: int, urgency: Urgency) -> bool:
    return days_until_slot <= URGENCY_WINDOW_DAYS[urgency]


def availability_score(days_until_slot: int, urgency: Urgency) -> float:
    """1.0 for same-day, falling linearly to 0.0 at the edge of the urgency window."""
    window = URGENCY_WINDOW_DAYS[urgency]
    if days_until_slot <= 0:
        return 1.0
    if days_until_slot >= window:
        return 0.0
    return (window - days_until_slot) / window


def select_weight_profile(urgency: Urgency, complexity: Complexity) -> WeightProfile:
    """Only URGENT (not SOON) switches profile; SOON scores like ROUTINE with a tighter window."""
    urgent = urgency == Urgency.URGENT
    rare = complexity == Complexity.RARE_COMPLEX
    if urgent and rare:
        return WeightProfile.URGENT_RARE_COMPLEX
    if urgent:
        return WeightProfile.URGENT
    if rare:
        return WeightProfile.RARE_COMPLEX
    return WeightProfile.ROUTINE
