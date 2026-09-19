"""Pydantic schemas. These ARE the API contract -- `openapi.json` is generated from them."""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

Role = Literal["referring_physician", "specialist", "admin"]
Urgency = Literal["routine", "urgent", "emergent"]
ReferralStatus = Literal["pending", "accepted", "declined", "scheduled"]


class User(BaseModel):
    id: str
    name: str
    role: Role
    city: str
    lat: float
    lng: float


class Specialist(BaseModel):
    id: str
    name: str
    specialty: str
    subspecialties: List[str]
    hospital: str
    city: str
    lat: float
    lng: float
    accepting_referrals: bool


class Slot(BaseModel):
    id: str
    specialist_id: str
    starts_at: str  # ISO 8601
    booked: bool = False


class CaseCreate(BaseModel):
    title: str = Field(min_length=1)
    patient_age: int = Field(ge=0, le=130)
    patient_sex: Literal["F", "M", "X"]
    urgency: Urgency = "routine"
    notes: str = Field(min_length=1, description="Free-text clinical notes")


class ParsedCase(BaseModel):
    """What the AI layer extracts from free-text notes."""

    condition: str
    specialty: str
    keywords: List[str]


class Case(CaseCreate):
    id: str
    created_at: str
    referring_physician_id: str


class Trial(BaseModel):
    nct_id: str
    title: str
    condition: str
    phase: str
    location: str
    url: str


class SpecialistMatch(BaseModel):
    specialist: Specialist
    score: float = Field(description="0-1, higher is a better fit")
    distance_km: float
    rationale: str
    next_slot: Optional[Slot] = None


class MatchResult(BaseModel):
    case_id: str
    parsed: ParsedCase
    specialists: List[SpecialistMatch]
    trials: List[Trial]


class ReferralCreate(BaseModel):
    case_id: str
    specialist_id: str
    note: str = ""


class Referral(ReferralCreate):
    id: str
    status: ReferralStatus
    created_at: str
    appointment_slot_id: Optional[str] = None


class AppointmentCreate(BaseModel):
    referral_id: str
    slot_id: str


class ConsultMessage(BaseModel):
    id: str
    consult_id: str
    sender_id: str
    sender_name: str
    body: str
    sent_at: str


class Consult(BaseModel):
    id: str
    specialist: Specialist
    last_message: Optional[ConsultMessage] = None
