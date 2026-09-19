"""Data access. Returns Pydantic contract models, never ORM rows."""

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import (
    MatchRunRow,
    PatientRow,
    PhysicianRow,
    ReferralRow,
    SpecialistRow,
)
from app.models.enums import Complexity, JobStatus, ReferralStatus, Urgency, WeightProfile
from app.models.match import MatchResult, MatchRun, TooLateCandidate
from app.models.people import GeoPoint, InsurancePlan, Patient, Physician, Specialist
from app.models.referral import Approval, ParsedCase, Referral, ReferralCreate
from app.models.scheduling import Appointment


def _now() -> datetime:
    return datetime.now(UTC)


def _utc(dt: datetime | None) -> datetime | None:
    # SQLite drops tzinfo; everything we store is UTC.
    return dt if dt is None or dt.tzinfo else dt.replace(tzinfo=UTC)


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def _physician(r: PhysicianRow) -> Physician:
    return Physician(id=r.id, name=r.name, specialty=r.specialty, practice_name=r.practice_name)


def _patient(r: PatientRow) -> Patient:
    return Patient(
        id=r.id,
        display_name=r.display_name,
        age=r.age,
        zip_code=r.zip_code,
        location=GeoPoint(lat=r.lat, lng=r.lng),
        insurance=InsurancePlan(payer=r.payer, plan_name=r.plan_name),
    )


def _specialist(r: SpecialistRow) -> Specialist:
    return Specialist(
        id=r.id,
        name=r.name,
        specialty=r.specialty,
        subspecialties=r.subspecialties,
        practice_name=r.practice_name,
        address=r.address,
        location=GeoPoint(lat=r.lat, lng=r.lng),
    )


def _referral(r: ReferralRow) -> Referral:
    return Referral(
        id=r.id,
        patient_id=r.patient_id,
        referring_physician_id=r.referring_physician_id,
        case_notes=r.case_notes,
        urgency=Urgency(r.urgency),
        complexity=Complexity(r.complexity) if r.complexity else None,
        parsed_case=ParsedCase.model_validate(r.parsed_case) if r.parsed_case else None,
        status=ReferralStatus(r.status),
        approval=Approval.model_validate(r.approval) if r.approval else None,
        appointment=Appointment.model_validate(r.appointment) if r.appointment else None,
        created_at=_utc(r.created_at),
        updated_at=_utc(r.updated_at),
    )


def _match_run(r: MatchRunRow) -> MatchRun:
    return MatchRun(
        id=r.id,
        referral_id=r.referral_id,
        status=JobStatus(r.status),
        weight_profile=WeightProfile(r.weight_profile) if r.weight_profile else None,
        degraded=r.degraded,
        results=[MatchResult.model_validate(x) for x in r.results],
        too_late=[TooLateCandidate.model_validate(x) for x in r.too_late],
        error=r.error,
        created_at=_utc(r.created_at),
        completed_at=_utc(r.completed_at),
    )


def _dump(model) -> dict | None:
    return None if model is None else model.model_dump(mode="json")


class Repository:
    def __init__(self, session: AsyncSession):
        self._s = session

    # ---- directory -------------------------------------------------------------------------

    async def physicians(self) -> list[Physician]:
        rows = await self._s.scalars(select(PhysicianRow).order_by(PhysicianRow.id))
        return [_physician(r) for r in rows]

    async def physician(self, physician_id: str) -> Physician | None:
        row = await self._s.get(PhysicianRow, physician_id)
        return _physician(row) if row else None

    async def patients(self) -> list[Patient]:
        rows = await self._s.scalars(select(PatientRow).order_by(PatientRow.id))
        return [_patient(r) for r in rows]

    async def patient(self, patient_id: str) -> Patient | None:
        row = await self._s.get(PatientRow, patient_id)
        return _patient(row) if row else None

    async def specialists(self) -> list[Specialist]:
        rows = await self._s.scalars(select(SpecialistRow).order_by(SpecialistRow.id))
        return [_specialist(r) for r in rows]

    async def specialist(self, specialist_id: str) -> Specialist | None:
        row = await self._s.get(SpecialistRow, specialist_id)
        return _specialist(row) if row else None

    # ---- referrals -------------------------------------------------------------------------

    async def create_referral(
        self, data: ReferralCreate, referral_id: str | None = None
    ) -> Referral:
        now = _now()
        row = ReferralRow(
            id=referral_id or _new_id("ref"),
            patient_id=data.patient_id,
            referring_physician_id=data.referring_physician_id,
            case_notes=data.case_notes,
            urgency=data.urgency.value,
            status=ReferralStatus.DRAFT.value,
            created_at=now,
            updated_at=now,
        )
        self._s.add(row)
        await self._s.commit()
        return _referral(row)

    async def referrals(self) -> list[Referral]:
        rows = await self._s.scalars(select(ReferralRow).order_by(ReferralRow.created_at.desc()))
        return [_referral(r) for r in rows]

    async def referral(self, referral_id: str) -> Referral | None:
        row = await self._s.get(ReferralRow, referral_id)
        return _referral(row) if row else None

    async def save_referral(self, ref: Referral) -> Referral:
        row = await self._s.get(ReferralRow, ref.id)
        row.urgency = ref.urgency.value
        row.complexity = ref.complexity.value if ref.complexity else None
        row.parsed_case = _dump(ref.parsed_case)
        row.status = ref.status.value
        row.approval = _dump(ref.approval)
        row.appointment = _dump(ref.appointment)
        row.updated_at = _now()
        await self._s.commit()
        return _referral(row)

    # ---- match runs ------------------------------------------------------------------------

    async def create_match_run(self, referral_id: str) -> MatchRun:
        row = MatchRunRow(
            id=_new_id("match"),
            referral_id=referral_id,
            status=JobStatus.QUEUED.value,
            degraded=False,
            results=[],
            too_late=[],
            created_at=_now(),
        )
        self._s.add(row)
        await self._s.commit()
        return _match_run(row)

    async def match_run(self, run_id: str) -> MatchRun | None:
        row = await self._s.get(MatchRunRow, run_id)
        return _match_run(row) if row else None

    async def latest_match_run(self, referral_id: str) -> MatchRun | None:
        row = await self._s.scalar(
            select(MatchRunRow)
            .where(MatchRunRow.referral_id == referral_id)
            .order_by(MatchRunRow.created_at.desc())
            .limit(1)
        )
        return _match_run(row) if row else None

    async def save_match_run(self, run: MatchRun) -> MatchRun:
        row = await self._s.get(MatchRunRow, run.id)
        row.status = run.status.value
        row.weight_profile = run.weight_profile.value if run.weight_profile else None
        row.degraded = run.degraded
        row.results = [r.model_dump(mode="json") for r in run.results]
        row.too_late = [t.model_dump(mode="json") for t in run.too_late]
        row.error = run.error
        row.completed_at = run.completed_at
        await self._s.commit()
        return _match_run(row)
