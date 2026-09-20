"""Tables for the few facts the core domain has no column for (see app/echo/__init__.py)."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base


class EchoPatientMetaRow(Base):
    """Display facts the frontend shows for a patient that the core `patients` table lacks."""

    __tablename__ = "echo_patient_meta"

    patient_id: Mapped[str] = mapped_column(String, primary_key=True)
    sex: Mapped[str] = mapped_column(String)  # F | M | X
    city: Mapped[str] = mapped_column(String)  # e.g. "Cambridge, MA"


class EchoReferralMetaRow(Base):
    """What the New Referral form submitted, plus the physician's selection and the patient's
    response. One row per referral created through /api/echo; older referrals have none and are
    described from the core data instead."""

    __tablename__ = "echo_referral_meta"

    referral_id: Mapped[str] = mapped_column(String, primary_key=True)
    reason: Mapped[str] = mapped_column(Text)
    details: Mapped[str] = mapped_column(Text)
    specialty: Mapped[str] = mapped_column(String)
    subspecialty: Mapped[str] = mapped_column(String, default="")  # "" = any subspecialty
    preferred_distance_miles: Mapped[int] = mapped_column(Integer)
    # Snapshots of what the physician submitted (they may differ from the patient record).
    patient_location: Mapped[str] = mapped_column(String)
    insurance: Mapped[str] = mapped_column(String)
    selected_specialist_id: Mapped[str | None] = mapped_column(String, nullable=True)
    selected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    patient_status: Mapped[str] = mapped_column(String, default="pending")
    patient_responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    pipeline_started: Mapped[bool] = mapped_column(Integer, default=0)
    analysis_error: Mapped[str | None] = mapped_column(Text, nullable=True)


class EchoSimulatedMessageRow(Base):
    """Consult messages written by the demo colleague simulator, not by a person. Kept here so the
    core message table stays untouched; the API marks these as demo replies."""

    __tablename__ = "echo_simulated_messages"

    message_id: Mapped[str] = mapped_column(String, primary_key=True)
