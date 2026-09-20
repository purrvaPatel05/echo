"""SQLAlchemy tables. Nested API objects (parsed case, results, ...) are stored as JSON."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class PhysicianRow(Base):
    __tablename__ = "physicians"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    specialty: Mapped[str] = mapped_column(String)
    practice_name: Mapped[str] = mapped_column(String)


class PatientRow(Base):
    __tablename__ = "patients"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(String)
    age: Mapped[int] = mapped_column(Integer)
    zip_code: Mapped[str] = mapped_column(String)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)
    payer: Mapped[str] = mapped_column(String)
    plan_name: Mapped[str] = mapped_column(String)


class SpecialistRow(Base):
    __tablename__ = "specialists"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    specialty: Mapped[str] = mapped_column(String, index=True)
    subspecialties: Mapped[list] = mapped_column(JSON)
    practice_name: Mapped[str] = mapped_column(String)
    address: Mapped[str] = mapped_column(String)
    lat: Mapped[float] = mapped_column(Float)
    lng: Mapped[float] = mapped_column(Float)


class ReferralRow(Base):
    __tablename__ = "referrals"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    patient_id: Mapped[str] = mapped_column(String, index=True)
    referring_physician_id: Mapped[str] = mapped_column(String, index=True)
    case_notes: Mapped[str] = mapped_column(Text)
    urgency: Mapped[str] = mapped_column(String)
    complexity: Mapped[str | None] = mapped_column(String, nullable=True)
    parsed_case: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String, index=True)
    approval: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    appointment: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    trial_approval: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SlotRow(Base):
    """An open appointment slot on a specialist's calendar. Generated at seed time from a
    recurring weekly template (see app.scheduling.generator); Member 3's scheduling service."""

    __tablename__ = "slots"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    specialist_id: Mapped[str] = mapped_column(String, index=True)
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    end: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AppointmentRow(Base):
    """A booked slot. `slot_id` is unique so a second concurrent booking attempt on the same
    slot fails the insert (IntegrityError -> SlotUnavailableError -> 409), not a race we resolve
    by locking."""

    __tablename__ = "appointments"
    __table_args__ = (UniqueConstraint("slot_id", name="uq_appointments_slot_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    slot_id: Mapped[str] = mapped_column(String, index=True)
    referral_id: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class SpecialistInsuranceRow(Base):
    """Mocked payer-network status per (specialist, payer). A lookup, not a live verification
    call -- there is no real payer API in this hackathon. A missing pair is treated as
    `unverified` rather than seeded, matching what a real integration would return when it has
    no contracting data for that pair."""

    __tablename__ = "specialist_insurance"
    __table_args__ = (
        UniqueConstraint("specialist_id", "payer", name="uq_specialist_insurance_specialist_payer"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    specialist_id: Mapped[str] = mapped_column(String, index=True)
    payer: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String)
    detail: Mapped[str] = mapped_column(String)


class ConsultThreadRow(Base):
    """A peer consult between two physicians. `referral_id` is optional case context, not a
    formal referral action -- the PRD's "even if it's not a formal referral" quick question."""

    __tablename__ = "consult_threads"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    initiator_physician_id: Mapped[str] = mapped_column(String, index=True)
    recipient_physician_id: Mapped[str] = mapped_column(String, index=True)
    referral_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ConsultMessageRow(Base):
    __tablename__ = "consult_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    thread_id: Mapped[str] = mapped_column(String, index=True)
    sender_physician_id: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class MatchRunRow(Base):
    __tablename__ = "match_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    referral_id: Mapped[str] = mapped_column(String, index=True)
    status: Mapped[str] = mapped_column(String)
    weight_profile: Mapped[str | None] = mapped_column(String, nullable=True)
    degraded: Mapped[bool] = mapped_column(Boolean, default=False)
    results: Mapped[list] = mapped_column(JSON, default=list)
    too_late: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
