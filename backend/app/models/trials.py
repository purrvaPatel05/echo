"""ClinicalTrials.gov (mocked): a static, synthetic trial list, not a live API call.

Trials are "a discussion option alongside the specialist recommendation, not a replacement"
(CLAUDE.md) -- a matched trial only reaches the patient once the referring physician explicitly
approves it (see TrialApproval / Referral.trial_approval), mirroring how specialist booking
requires explicit approval.
"""

from datetime import datetime

from pydantic import BaseModel


class Trial(BaseModel):
    id: str
    nct_id: str  # synthetic, ClinicalTrials.gov-style id; not a real registration
    title: str
    phase: str
    condition: str
    condition_keywords: list[str]  # matched against the parsed case's specialties/tags
    summary: str  # plain language, physician-facing
    eligibility_summary: str
    location: str


class TrialApproval(BaseModel):
    trial_id: str
    approved_by: str
    approved_at: datetime
