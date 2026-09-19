from datetime import datetime

from pydantic import BaseModel

from app.models.enums import (
    FactorName,
    FitTier,
    InsuranceStatus,
    JobStatus,
    Verdict,
    WeightProfile,
)
from app.models.people import Specialist
from app.models.scheduling import AppointmentSlot


class FactorResult(BaseModel):
    factor: FactorName
    verdict: Verdict
    score: float  # 0-1 sub-score
    weight: float  # weight applied under the run's profile
    detail: str  # e.g. "8.4 miles away"


class ClinicalFit(BaseModel):
    tier: FitTier
    rationale: str


class InsuranceCheck(BaseModel):
    status: InsuranceStatus
    detail: str  # e.g. "In-network with Aetna PPO"


class MatchResult(BaseModel):
    rank: int
    specialist: Specialist
    match_percent: int  # weighted sum of sub-scores, 0-100
    clinical_fit: ClinicalFit  # shown separately from the overall score
    insurance: InsuranceCheck
    distance_miles: float
    earliest_slot: AppointmentSlot | None
    days_until_slot: int | None
    factors: list[FactorResult]
    explanation: str
    why_not_first: str | None = None  # rank > 1: "Closer, but weaker match"


class TooLateCandidate(BaseModel):
    """Passed every other gate but the earliest slot is outside the urgency window."""

    specialist: Specialist
    earliest_slot: AppointmentSlot | None
    detail: str


class MatchRun(BaseModel):
    id: str
    referral_id: str
    status: JobStatus
    weight_profile: WeightProfile | None = None
    degraded: bool = False  # True when Claude was unavailable and rules-only matching was used
    results: list[MatchResult] = []
    too_late: list[TooLateCandidate] = []
    error: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
