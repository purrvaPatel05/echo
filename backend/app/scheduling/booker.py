"""Real Booker (app.booking.Booker), backed by the slots/appointments tables this package owns.

Opens its own short-lived session per booking, mirroring app/jobs.py and the Celery tasks in
app/celery_app.py, which each manage their own session rather than sharing one across
requests/event loops.
"""

from app.booking import SlotUnavailableError
from app.db.repository import Repository
from app.db.session import SessionFactory
from app.models.referral import Referral
from app.models.scheduling import Appointment


class DbBooker:
    def __init__(self, session_factory: SessionFactory):
        self._session_factory = session_factory

    async def book(self, referral: Referral, specialist_id: str, slot_id: str) -> Appointment:
        async with self._session_factory() as session:
            repo = Repository(session)
            slot = await repo.slot(slot_id)
            if slot is None or slot.specialist_id != specialist_id:
                raise SlotUnavailableError(f"Slot {slot_id} is not available for {specialist_id}")
            return await repo.book_slot(slot_id, referral.id)
