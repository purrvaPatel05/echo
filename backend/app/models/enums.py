"""Enums shared across the API contract, matching engine, and (via OpenAPI) the frontend."""

from enum import StrEnum


class Urgency(StrEnum):
    ROUTINE = "routine"
    SOON = "soon"
    URGENT = "urgent"


class Complexity(StrEnum):
    """Claude proposes this at parse time; the physician confirms or overrides before matching."""

    ROUTINE = "routine"
    RARE_COMPLEX = "rare_complex"


class InsuranceStatus(StrEnum):
    IN_NETWORK = "in_network"
    UNVERIFIED = "unverified"
    OUT_OF_NETWORK = "out_of_network"
    NOT_ACCEPTED = "not_accepted"  # gated out of the ranked list


class FitTier(StrEnum):
    """Claude's clinical-fit judgment for a (case, specialist) pair."""

    EXCELLENT = "excellent"
    GOOD = "good"
    PARTIAL = "partial"
    POOR = "poor"  # gated out of the ranked list


class ReferralStatus(StrEnum):
    """approved/booked require an explicit physician action."""

    DRAFT = "draft"
    MATCHED = "matched"
    APPROVED = "approved"
    BOOKED = "booked"
    WAITLISTED = "waitlisted"
    CANCELLED = "cancelled"


class JobStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class WeightProfile(StrEnum):
    ROUTINE = "routine"
    URGENT = "urgent"
    RARE_COMPLEX = "rare_complex"
    URGENT_RARE_COMPLEX = "urgent_rare_complex"  # average of the urgent and rare_complex profiles


class FactorName(StrEnum):
    CLINICAL_FIT = "clinical_fit"
    INSURANCE = "insurance"
    DISTANCE = "distance"
    AVAILABILITY = "availability"


class Verdict(StrEnum):
    """How the UI renders a factor line: ✓ / ⚠ / ?"""

    GOOD = "good"
    CAUTION = "caution"
    UNKNOWN = "unknown"
