"""Shapes shared with Member 3, who owns the scheduling service that produces them."""

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import ReferralStatus


class AppointmentSlot(BaseModel):
    id: str
    specialist_id: str
    start: datetime
    end: datetime


class Appointment(BaseModel):
    id: str
    referral_id: str
    slot: AppointmentSlot
    status: ReferralStatus  # BOOKED or WAITLISTED
