"""Booking seam. Booking mechanics belong to Member 3's scheduling service.

Nothing implements `Booker` yet: until it does, approving a referral records the physician's
approval (status `approved`) without creating an appointment. Once a booker is provided via
`app.deps.get_booker`, approval books through it and the referral becomes `booked`.
"""

from typing import Protocol

from app.models.referral import Referral
from app.models.scheduling import Appointment


class SlotUnavailableError(Exception):
    """The chosen slot was taken between matching and approval."""


class Booker(Protocol):
    async def book(self, referral: Referral, specialist_id: str, slot_id: str) -> Appointment:
        """Raise SlotUnavailableError if the slot is gone."""
        ...
