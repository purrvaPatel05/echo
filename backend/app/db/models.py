"""SQLAlchemy tables. Nested API objects (parsed case, results, ...) are stored as JSON."""

from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, Float, Integer, String, Text
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
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


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
