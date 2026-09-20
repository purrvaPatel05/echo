from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.models.enums import Complexity, ReferralStatus, Urgency
from app.models.scheduling import Appointment
from app.models.trials import TrialApproval


class ParsedCase(BaseModel):
    """Claude's (or the rules fallback's) reading of the case notes. Suggestions only:
    the physician confirms urgency and complexity before matching."""

    condition_summary: str
    suggested_specialties: list[str]
    subspecialty_tags: list[str]
    red_flags: list[str] = []
    suggested_urgency: Urgency
    suggested_complexity: Complexity
    rationale: str
    source: Literal["claude", "rules_fallback"]


class Approval(BaseModel):
    specialist_id: str
    slot_id: str
    approved_by: str  # always recorded: the signed-in physician
    approved_at: datetime


class ReferralCreate(BaseModel):
    patient_id: str
    # Optional: the referring physician is the signed-in user. If sent, it must match (else 403).
    referring_physician_id: str | None = None
    case_notes: str = Field(min_length=1)
    urgency: Urgency = Urgency.ROUTINE

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "patient_id": "pat_001",
                    "case_notes": "58F, 3 months progressive right knee pain, worse on stairs. "
                    "Swelling after activity. No trauma. X-ray shows joint space narrowing.",
                    "urgency": "routine",
                }
            ]
        }
    }


class ReferralUpdate(BaseModel):
    """Physician confirmation/override. Matching requires both to be set (409 otherwise)."""

    urgency: Urgency | None = None
    complexity: Complexity | None = None


class Referral(BaseModel):
    id: str
    patient_id: str
    referring_physician_id: str
    case_notes: str
    urgency: Urgency
    complexity: Complexity | None = None  # None until the physician confirms
    parsed_case: ParsedCase | None = None  # None until parsing completes
    status: ReferralStatus
    approval: Approval | None = None
    appointment: Appointment | None = None
    trial_approval: TrialApproval | None = None  # set only once the physician approves a trial
    created_at: datetime
    updated_at: datetime


class ApproveRequest(BaseModel):
    """The physician's explicit approval. Booking happens only as a result of this call."""

    match_run_id: str
    specialist_id: str
    slot_id: str
    approved_by: str | None = None  # optional; if sent it must match the signed-in physician


class ApproveTrialRequest(BaseModel):
    """The physician's explicit approval to surface this trial to the patient."""

    approved_by: str | None = None  # optional; if sent it must match the signed-in physician


class PatientSummary(BaseModel):
    referral_id: str
    summary: str  # plain language: who they're referred to and why
    specialist_name: str | None = None
    appointment: Appointment | None = None
    cost_note: str | None = None  # set when insurance status isn't in_network
    trial_note: str | None = None  # physician-vetted only
