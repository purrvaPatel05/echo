"""Request/response shapes of /api/echo/*: the JSON the frontend's TypeScript types describe
(frontend/src/echo/types.ts), camelCase on the wire."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from app.models.enums import Urgency


class Wire(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


Sex = Literal["F", "M", "X"]
EchoStatus = Literal["awaiting_approval", "awaiting_patient", "scheduled"]


class Physician(Wire):
    id: str
    name: str
    specialty: str
    organization: str


class Patient(Wire):
    id: str
    name: str
    age: int
    sex: Sex
    insurance: str
    location: str


class SpecialtyOption(Wire):
    name: str
    subspecialties: list[str]


class ReferralOptions(Wire):
    specialties: list[SpecialtyOption]
    insurers: list[str]
    distances_miles: list[int]


class SpecialistSummary(Wire):
    id: str
    name: str
    specialty: str
    subspecialty: str
    organization: str
    city: str | None = None


class PatientConfirmation(Wire):
    status: Literal["pending", "confirmed", "declined"]
    responded_at: str | None


class TimelineEvent(Wire):
    kind: str
    at: str


class Attention(Wire):
    reason: str
    action: str


class Referral(Wire):
    id: str
    patient: Patient
    reason: str
    details: str
    preferred_distance_miles: int
    specialty: str
    subspecialty: str
    urgency: Urgency
    status: EchoStatus
    created_at: str
    specialist: SpecialistSummary | None
    appointment_at: str | None
    attention: Attention | None
    insurance_accepted: bool | None = None
    patient_confirmation: PatientConfirmation
    timeline: list[TimelineEvent]


class NewReferralInput(Wire):
    patient_id: str
    patient_location: str = Field(min_length=1)
    insurance: str = Field(min_length=1)
    specialty: str = Field(min_length=1)
    subspecialty: str | None = None
    preferred_distance_miles: int = Field(gt=0)
    urgency: Urgency
    reason: str = Field(min_length=1)
    details: str = Field(min_length=1)


class AnalysisCheck(Wire):
    key: Literal["clinical_fit", "insurance", "distance", "urgency", "availability"]
    state: Literal["done", "active", "waiting", "error"]


class Analysis(Wire):
    referral_id: str
    status: Literal["running", "complete", "error"]
    checks: list[AnalysisCheck]
    match_count: int | None


class MatchFactor(Wire):
    key: Literal["clinical_fit", "insurance", "distance", "availability", "urgency"]
    status: Literal["met", "partial", "unmet"]
    detail: str


class Slot(Wire):
    id: str
    starts_at: str


class SpecialistMatch(Wire):
    specialist: SpecialistSummary
    distance_miles: float
    strength: Literal["strong", "good", "partial"]
    factors: list[MatchFactor]
    why: str
    next_slot: Slot | None


class MatchesResult(Wire):
    referral_id: str
    search_distance_miles: int
    matches: list[SpecialistMatch]
    no_match_reason: str | None


class ApproveInput(Wire):
    specialist_id: str
    slot_id: str


class SelectInput(Wire):
    specialist_id: str


class PatientResponseInput(Wire):
    status: Literal["confirmed", "declined"]


class Colleague(Wire):
    id: str
    name: str
    specialty: str
    organization: str


class ConsultContext(Wire):
    """What a colleague is given about a case: age, sex, reason and summary. Never the name."""

    age: int
    sex: Sex
    reason: str
    summary: str


class ConsultReferralRef(Wire):
    """The referral a consult is about, as its sender sees it (the sender may see the name)."""

    id: str
    patient_name: str
    age: int
    sex: Sex
    reason: str


class ConsultLastMessage(Wire):
    text: str
    at: str
    from_me: bool


class ConsultMessage(Wire):
    id: str
    from_me: bool
    text: str
    at: str
    simulated: bool = False  # a demo reply written by the simulator, not by a person


class ConsultSummary(Wire):
    """One row of the conversation list. `pending` = the last message is mine and unanswered."""

    id: str
    colleague: Colleague
    referral: ConsultReferralRef | None  # only for consults I started, and only if one is attached
    status: Literal["pending", "responded"]
    last_message: ConsultLastMessage


class ConsultThread(ConsultSummary):
    messages: list[ConsultMessage]
    shared_context: ConsultContext | None  # set when a referral is attached


class StartConsultInput(Wire):
    colleague_id: str
    text: str = Field(min_length=1)
    referral_id: str | None = None  # optional: a consult does not need a referral


class SendMessageInput(Wire):
    text: str = Field(min_length=1)


class TrialCriteria(Wire):
    condition: str
    patient: str
    location: str
    status: str
    source: str
    distance_miles: int | None
    all_statuses: bool


class Trial(Wire):
    nct_id: str
    title: str
    condition: str
    intervention: str
    location: str
    distance_miles: float | None
    status: Literal["recruiting", "not_yet_recruiting", "active_not_recruiting"]
    relevance: str | None
    url: str


class TrialsResult(Wire):
    referral_id: str
    trials: list[Trial]


class AuthConfig(Wire):
    login: bool  # true: the frontend must show the login page (AUTH_MODE=session)
    demo_accounts: bool  # true: the one-click "Demo accounts" list is available


class LoginInput(Wire):
    email: str
    password: str


class DemoLoginInput(Wire):
    physician_id: str


class DemoAccount(Wire):
    id: str
    name: str
    specialty: str
    organization: str
    email: str  # what to type on the login page (with the demo password)


class Session(Wire):
    token: str
    physician: Physician
