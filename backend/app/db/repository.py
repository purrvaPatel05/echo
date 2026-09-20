"""Data access. Returns Pydantic contract models, never ORM rows."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.booking import SlotUnavailableError
from app.db.models import (
    AppointmentRow,
    ConsultMessageRow,
    ConsultThreadRow,
    MatchRunRow,
    PatientRow,
    PhysicianRow,
    ReferralRow,
    SlotRow,
    SpecialistInsuranceRow,
    SpecialistRow,
)
from app.models.consult import ConsultMessage, ConsultThread
from app.models.enums import (
    Complexity,
    InsuranceStatus,
    JobStatus,
    ReferralStatus,
    Urgency,
    WeightProfile,
)
from app.models.match import InsuranceCheck, MatchResult, MatchRun, TooLateCandidate
from app.models.people import GeoPoint, InsurancePlan, Patient, Physician, Specialist
from app.models.referral import Approval, ParsedCase, Referral, ReferralCreate
from app.models.scheduling import Appointment, AppointmentSlot
from app.models.trials import TrialApproval


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
        trial_approval=TrialApproval.model_validate(r.trial_approval) if r.trial_approval else None,
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


def _slot(r: SlotRow) -> AppointmentSlot:
    return AppointmentSlot(
        id=r.id, specialist_id=r.specialist_id, start=_utc(r.start), end=_utc(r.end)
    )


_UNVERIFIED_DETAIL = (
    "Coverage with {payer} is unverified for this specialist; confirm with the plan."
)


def _consult_message(r: ConsultMessageRow) -> ConsultMessage:
    return ConsultMessage(
        id=r.id,
        thread_id=r.thread_id,
        sender_physician_id=r.sender_physician_id,
        body=r.body,
        created_at=_utc(r.created_at),
        read_at=_utc(r.read_at),
    )


def _consult_thread(
    r: ConsultThreadRow, last_message: ConsultMessage | None = None, unread_count: int = 0
) -> ConsultThread:
    return ConsultThread(
        id=r.id,
        initiator_physician_id=r.initiator_physician_id,
        recipient_physician_id=r.recipient_physician_id,
        referral_id=r.referral_id,
        created_at=_utc(r.created_at),
        last_message=last_message,
        unread_count=unread_count,
    )


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

    async def referrals(self, physician_id: str | None = None) -> list[Referral]:
        query = select(ReferralRow).order_by(ReferralRow.created_at.desc())
        if physician_id is not None:
            query = query.where(ReferralRow.referring_physician_id == physician_id)
        rows = await self._s.scalars(query)
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
        row.trial_approval = _dump(ref.trial_approval)
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

    # ---- scheduling (Member 3) --------------------------------------------------------------

    async def create_slots(self, slots: Sequence[AppointmentSlot]) -> None:
        """Idempotent bulk insert, used by seeding. Skips ids already present."""
        existing = set(await self._s.scalars(select(SlotRow.id)))
        self._s.add_all(
            SlotRow(id=s.id, specialist_id=s.specialist_id, start=s.start, end=s.end)
            for s in slots
            if s.id not in existing
        )
        await self._s.commit()

    async def slot(self, slot_id: str) -> AppointmentSlot | None:
        row = await self._s.get(SlotRow, slot_id)
        return _slot(row) if row else None

    async def open_slots(
        self, specialist_id: str, after: datetime, limit: int | None = None
    ) -> list[AppointmentSlot]:
        """Slots for the specialist starting at/after `after` with no appointment against them."""
        booked = select(AppointmentRow.slot_id)
        query = (
            select(SlotRow)
            .where(SlotRow.specialist_id == specialist_id)
            .where(SlotRow.start >= after)
            .where(SlotRow.id.notin_(booked))
            .order_by(SlotRow.start)
        )
        if limit is not None:
            query = query.limit(limit)
        rows = await self._s.scalars(query)
        return [_slot(r) for r in rows]

    async def earliest_open_slot(
        self, specialist_id: str, after: datetime
    ) -> AppointmentSlot | None:
        slots = await self.open_slots(specialist_id, after, limit=1)
        return slots[0] if slots else None

    async def book_slot(self, slot_id: str, referral_id: str) -> Appointment:
        """Atomically claims the slot: a unique constraint on `slot_id` makes a second concurrent
        booking attempt fail at the DB level rather than via an explicit lock."""
        slot_row = await self._s.get(SlotRow, slot_id)
        if slot_row is None:
            raise SlotUnavailableError(f"Slot {slot_id} does not exist")
        slot = _slot(slot_row)  # read now: a rollback below expires the row
        # Booking commits before the referral is saved as booked (a separate step), so a retry
        # after a failure in between finds the slot already held by this same referral. That is
        # the same booking, not a conflict: return it instead of failing.
        held = await self._appointment_on_slot(slot_id)
        if held is not None:
            return self._held_or_unavailable(held, slot, referral_id)
        appt_row = AppointmentRow(
            id=_new_id("appt"),
            slot_id=slot_id,
            referral_id=referral_id,
            status=ReferralStatus.BOOKED.value,
            created_at=_now(),
        )
        self._s.add(appt_row)
        try:
            await self._s.commit()
        except IntegrityError:
            await self._s.rollback()
            # Lost a race for the slot. If the winner is this same referral (two retries at once),
            # it is still one booking.
            held = await self._appointment_on_slot(slot_id)
            if held is None:
                raise SlotUnavailableError(f"Slot {slot_id} is already booked") from None
            return self._held_or_unavailable(held, slot, referral_id)
        return Appointment(
            id=appt_row.id,
            referral_id=referral_id,
            slot=slot,
            status=ReferralStatus.BOOKED,
        )

    async def _appointment_on_slot(self, slot_id: str) -> AppointmentRow | None:
        return await self._s.scalar(
            select(AppointmentRow)
            .where(AppointmentRow.slot_id == slot_id)
            .execution_options(populate_existing=True)
        )

    @staticmethod
    def _held_or_unavailable(
        held: AppointmentRow, slot: AppointmentSlot, referral_id: str
    ) -> Appointment:
        if held.referral_id != referral_id:
            raise SlotUnavailableError(f"Slot {held.slot_id} is already booked")
        return Appointment(
            id=held.id,
            referral_id=referral_id,
            slot=slot,
            status=ReferralStatus(held.status),
        )

    # ---- insurance network (Member 3) -------------------------------------------------------

    async def create_insurance_status(
        self, specialist_id: str, payer: str, status: InsuranceStatus, detail: str
    ) -> None:
        """Idempotent upsert-by-lookup, used by seeding."""
        row = await self._s.scalar(
            select(SpecialistInsuranceRow).where(
                SpecialistInsuranceRow.specialist_id == specialist_id,
                SpecialistInsuranceRow.payer == payer,
            )
        )
        if row is None:
            self._s.add(
                SpecialistInsuranceRow(
                    id=_new_id("ins"),
                    specialist_id=specialist_id,
                    payer=payer,
                    status=status.value,
                    detail=detail,
                )
            )
            await self._s.commit()

    async def insurance_status(self, specialist_id: str, payer: str) -> InsuranceCheck:
        row = await self._s.scalar(
            select(SpecialistInsuranceRow).where(
                SpecialistInsuranceRow.specialist_id == specialist_id,
                SpecialistInsuranceRow.payer == payer,
            )
        )
        if row is None:
            return InsuranceCheck(
                status=InsuranceStatus.UNVERIFIED, detail=_UNVERIFIED_DETAIL.format(payer=payer)
            )
        return InsuranceCheck(status=InsuranceStatus(row.status), detail=row.detail)

    # ---- peer consult (Member 3) -------------------------------------------------------------

    async def create_consult_thread(
        self, initiator_physician_id: str, recipient_physician_id: str, referral_id: str | None
    ) -> ConsultThread:
        row = ConsultThreadRow(
            id=_new_id("consult"),
            initiator_physician_id=initiator_physician_id,
            recipient_physician_id=recipient_physician_id,
            referral_id=referral_id,
            created_at=_now(),
        )
        self._s.add(row)
        await self._s.commit()
        return _consult_thread(row)

    async def consult_thread(self, thread_id: str) -> ConsultThread | None:
        row = await self._s.get(ConsultThreadRow, thread_id)
        return _consult_thread(row) if row else None

    async def threads_for(self, physician_id: str) -> list[ConsultThread]:
        """Threads the physician is a participant in, newest first, each with its last message
        and an unread count relative to `physician_id`."""
        rows = await self._s.scalars(
            select(ConsultThreadRow)
            .where(
                or_(
                    ConsultThreadRow.initiator_physician_id == physician_id,
                    ConsultThreadRow.recipient_physician_id == physician_id,
                )
            )
            .order_by(ConsultThreadRow.created_at.desc())
        )
        threads = []
        for row in rows:
            last = await self._s.scalar(
                select(ConsultMessageRow)
                .where(ConsultMessageRow.thread_id == row.id)
                .order_by(ConsultMessageRow.created_at.desc())
                .limit(1)
            )
            unread = await self._s.scalar(
                select(func.count())
                .select_from(ConsultMessageRow)
                .where(
                    ConsultMessageRow.thread_id == row.id,
                    ConsultMessageRow.sender_physician_id != physician_id,
                    ConsultMessageRow.read_at.is_(None),
                )
            )
            threads.append(
                _consult_thread(
                    row,
                    last_message=_consult_message(last) if last else None,
                    unread_count=unread or 0,
                )
            )
        return threads

    async def create_consult_message(
        self, thread_id: str, sender_physician_id: str, body: str
    ) -> ConsultMessage:
        row = ConsultMessageRow(
            id=_new_id("cmsg"),
            thread_id=thread_id,
            sender_physician_id=sender_physician_id,
            body=body,
            created_at=_now(),
        )
        self._s.add(row)
        await self._s.commit()
        return _consult_message(row)

    async def consult_messages(self, thread_id: str) -> list[ConsultMessage]:
        rows = await self._s.scalars(
            select(ConsultMessageRow)
            .where(ConsultMessageRow.thread_id == thread_id)
            .order_by(ConsultMessageRow.created_at)
        )
        return [_consult_message(r) for r in rows]

    async def mark_consult_read(self, thread_id: str, reader_physician_id: str) -> None:
        """Marks every message in the thread not sent by the reader as read by them."""
        rows = await self._s.scalars(
            select(ConsultMessageRow).where(
                ConsultMessageRow.thread_id == thread_id,
                ConsultMessageRow.sender_physician_id != reader_physician_id,
                ConsultMessageRow.read_at.is_(None),
            )
        )
        now = _now()
        for row in rows:
            row.read_at = now
        await self._s.commit()
