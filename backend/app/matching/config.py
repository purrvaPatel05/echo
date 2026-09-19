"""Every tunable number in the matching engine lives here.

These are starting guesses with no clinical basis (see CLAUDE.md). Have a physician
sanity-check them before any real use.
"""

from app.models.enums import FactorName, FitTier, InsuranceStatus, Urgency, WeightProfile

# Gate: the earliest slot must fall within this many days of the referral.
URGENCY_WINDOW_DAYS: dict[Urgency, int] = {
    Urgency.URGENT: 3,
    Urgency.SOON: 14,
    Urgency.ROUTINE: 60,
}

# Gates: POOR clinical fit and NOT_ACCEPTED insurance never reach scoring (absent from these maps).
FIT_TIER_SCORE: dict[FitTier, float] = {
    FitTier.EXCELLENT: 1.0,
    FitTier.GOOD: 0.7,
    FitTier.PARTIAL: 0.35,
}
INSURANCE_SCORE: dict[InsuranceStatus, float] = {
    InsuranceStatus.IN_NETWORK: 1.0,
    InsuranceStatus.UNVERIFIED: 0.5,
    InsuranceStatus.OUT_OF_NETWORK: 0.3,
}

# Distance curve (miles): full marks up to FULL, linearly down to zero at ZERO.
DISTANCE_FULL_MILES = 5.0
DISTANCE_ZERO_MILES = 50.0

# A sub-score at or above this renders as a good (✓) factor line; below it, as caution (⚠).
VERDICT_GOOD_MIN_SCORE = 0.5

_F = FactorName
WEIGHTS_ROUTINE = {
    _F.CLINICAL_FIT: 0.50,
    _F.AVAILABILITY: 0.20,
    _F.INSURANCE: 0.15,
    _F.DISTANCE: 0.15,
}
WEIGHTS_URGENT = {
    _F.CLINICAL_FIT: 0.40,
    _F.AVAILABILITY: 0.35,
    _F.INSURANCE: 0.10,
    _F.DISTANCE: 0.15,
}
WEIGHTS_RARE_COMPLEX = {
    _F.CLINICAL_FIT: 0.65,
    _F.AVAILABILITY: 0.10,
    _F.INSURANCE: 0.10,
    _F.DISTANCE: 0.15,
}
# A case that is both urgent and rare/complex: the average of the two profiles (still sums to 1).
WEIGHTS_URGENT_RARE_COMPLEX = {
    f: (WEIGHTS_URGENT[f] + WEIGHTS_RARE_COMPLEX[f]) / 2 for f in WEIGHTS_URGENT
}

WEIGHT_PROFILES: dict[WeightProfile, dict[FactorName, float]] = {
    WeightProfile.ROUTINE: WEIGHTS_ROUTINE,
    WeightProfile.URGENT: WEIGHTS_URGENT,
    WeightProfile.RARE_COMPLEX: WEIGHTS_RARE_COMPLEX,
    WeightProfile.URGENT_RARE_COMPLEX: WEIGHTS_URGENT_RARE_COMPLEX,
}
