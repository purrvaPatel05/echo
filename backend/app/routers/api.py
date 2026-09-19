"""All REST endpoints. Split into more router files as this grows."""
import asyncio
from typing import List, Optional

from fastapi import APIRouter, HTTPException

from .. import realtime, store
from ..models import (
    AppointmentCreate,
    Case,
    CaseCreate,
    Consult,
    ConsultMessage,
    MatchResult,
    Referral,
    ReferralCreate,
    ReferralStatus,
    Slot,
    Specialist,
    User,
)
from ..services import matching

router = APIRouter(prefix="/api")


@router.get("/health", tags=["meta"])
def health():
    return {"status": "ok"}


@router.get("/me", response_model=User, tags=["auth"])
def me():
    # Real version: verify Auth0/Firebase JWT, load role from claims.
    return store.CURRENT_USER


# --- specialists -------------------------------------------------------------
@router.get("/specialists", response_model=List[Specialist], tags=["specialists"])
def list_specialists(specialty: Optional[str] = None):
    specs = list(store.SPECIALISTS.values())
    if specialty:
        specs = [s for s in specs if s.specialty.lower() == specialty.lower()]
    return specs


# --- cases -------------------------------------------------------------------
@router.get("/cases", response_model=List[Case], tags=["cases"])
def list_cases():
    return sorted(store.CASES.values(), key=lambda c: c.created_at, reverse=True)


@router.post("/cases", response_model=Case, status_code=201, tags=["cases"])
def create_case(body: CaseCreate):
    case = Case(
        **body.model_dump(), id=store.new_id("case"), created_at=store.now_iso(),
        referring_physician_id=store.CURRENT_USER.id,
    )
    store.CASES[case.id] = case
    return case


def _get_case(case_id: str) -> Case:
    case = store.CASES.get(case_id)
    if not case:
        raise HTTPException(404, "Case not found")
    return case


@router.get("/cases/{case_id}", response_model=Case, tags=["cases"])
def get_case(case_id: str):
    return _get_case(case_id)


@router.post("/cases/{case_id}/match", response_model=MatchResult, tags=["cases"])
def match_case(case_id: str):
    """Parse notes -> guardrail + rank specialists -> look up trials.

    Synchronous in the mock. In production this enqueues a Celery job.
    """
    case = _get_case(case_id)
    parsed = matching.parse_case(case)
    return MatchResult(
        case_id=case.id,
        parsed=parsed,
        specialists=matching.rank_specialists(case, parsed, store.CURRENT_USER),
        trials=matching.find_trials(parsed),
    )


# --- referrals ---------------------------------------------------------------
@router.get("/referrals", response_model=List[Referral], tags=["referrals"])
def list_referrals():
    return sorted(store.REFERRALS.values(), key=lambda r: r.created_at, reverse=True)


async def _mock_specialist_accepts(referral_id: str) -> None:
    await asyncio.sleep(4)
    ref = store.REFERRALS.get(referral_id)
    if ref and ref.status == "pending":
        ref.status = "accepted"
        await realtime.emit_referral_update(ref)


@router.post("/referrals", response_model=Referral, status_code=201, tags=["referrals"])
async def create_referral(body: ReferralCreate):
    _get_case(body.case_id)
    if body.specialist_id not in store.SPECIALISTS:
        raise HTTPException(404, "Specialist not found")
    ref = Referral(**body.model_dump(), id=store.new_id("ref"), status="pending", created_at=store.now_iso())
    store.REFERRALS[ref.id] = ref
    asyncio.create_task(_mock_specialist_accepts(ref.id))  # stand-in for the specialist acting
    return ref


@router.patch("/referrals/{referral_id}/status", response_model=Referral, tags=["referrals"])
async def set_referral_status(referral_id: str, status: ReferralStatus):
    ref = store.REFERRALS.get(referral_id)
    if not ref:
        raise HTTPException(404, "Referral not found")
    ref.status = status
    await realtime.emit_referral_update(ref)
    return ref


# --- scheduling (mocked slots table) ------------------------------------------
@router.get("/specialists/{specialist_id}/slots", response_model=List[Slot], tags=["scheduling"])
def list_slots(specialist_id: str):
    return [s for s in store.SLOTS.values() if s.specialist_id == specialist_id and not s.booked]


@router.post("/appointments", response_model=Referral, status_code=201, tags=["scheduling"])
async def book_appointment(body: AppointmentCreate):
    ref = store.REFERRALS.get(body.referral_id)
    slot = store.SLOTS.get(body.slot_id)
    if not ref or not slot:
        raise HTTPException(404, "Referral or slot not found")
    if slot.booked or slot.specialist_id != ref.specialist_id:
        raise HTTPException(409, "Slot unavailable")
    slot.booked = True
    ref.status = "scheduled"
    ref.appointment_slot_id = slot.id
    await realtime.emit_referral_update(ref)
    return ref


# --- consults ----------------------------------------------------------------
@router.get("/consults", response_model=List[Consult], tags=["consults"])
def list_consults():
    """One consult thread per specialist (id == specialist id) in the mock."""
    out = []
    for spec in store.SPECIALISTS.values():
        msgs = store.MESSAGES.get(spec.id, [])
        out.append(Consult(id=spec.id, specialist=spec, last_message=msgs[-1] if msgs else None))
    return out


@router.get("/consults/{consult_id}/messages", response_model=List[ConsultMessage], tags=["consults"])
def list_messages(consult_id: str):
    if consult_id not in store.SPECIALISTS:
        raise HTTPException(404, "Consult not found")
    return store.MESSAGES.get(consult_id, [])
