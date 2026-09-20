"""Pure generation of a specialist's open slots from a recurring weekly template. No I/O --
seeding calls this and persists the result via Repository.create_slots.
"""

import random
from datetime import UTC, date, datetime, time, timedelta

from app.models.scheduling import AppointmentSlot

SLOT_MINUTES = 30
BUSINESS_START = time(9, 0)
BUSINESS_END = time(17, 0)
WEEKS_AHEAD = 9  # ~63 days: safely covers the 60-day routine urgency window


def _day_slot_starts(day: date) -> list[datetime]:
    starts = []
    t = datetime.combine(day, BUSINESS_START, tzinfo=UTC)
    end = datetime.combine(day, BUSINESS_END, tzinfo=UTC)
    while t < end:
        starts.append(t)
        t += timedelta(minutes=SLOT_MINUTES)
    return starts


def generate_weekly_slots(
    specialist_id: str,
    start_date: date,
    fill_rate: float,
    *,
    weeks: int = WEEKS_AHEAD,
) -> list[AppointmentSlot]:
    """Weekday, business-hours slots for `weeks` weeks from `start_date`.

    `fill_rate` (0-1) is the fraction of slots already taken/blocked at seed time and so never
    offered as open -- higher means a busier, sparser calendar. Deterministic per specialist_id
    so re-seeding is idempotent.
    """
    rng = random.Random(specialist_id)
    slots = []
    for i in range(weeks * 7):
        day = start_date + timedelta(days=i)
        if day.weekday() >= 5:  # Saturday/Sunday
            continue
        for start in _day_slot_starts(day):
            if rng.random() < fill_rate:
                continue
            slots.append(
                AppointmentSlot(
                    id=f"slot_{specialist_id}_{start:%Y%m%dT%H%M}",
                    specialist_id=specialist_id,
                    start=start,
                    end=start + timedelta(minutes=SLOT_MINUTES),
                )
            )
    return slots
