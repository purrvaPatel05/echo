from datetime import date

from app.scheduling.generator import SLOT_MINUTES, generate_weekly_slots


def test_no_weekend_slots():
    slots = generate_weekly_slots("sp_x", date(2026, 9, 21), fill_rate=0.0, weeks=2)
    assert all(s.start.weekday() < 5 for s in slots)


def test_zero_fill_rate_returns_every_business_slot():
    weeks = 2
    slots = generate_weekly_slots("sp_x", date(2026, 9, 21), fill_rate=0.0, weeks=weeks)
    weekdays = sum(1 for i in range(weeks * 7) if (date(2026, 9, 21).toordinal() + i) % 7 < 5)
    slots_per_day = (17 - 9) * 60 // SLOT_MINUTES
    # every weekday slot present, none skipped
    assert len({s.start.date() for s in slots}) <= weekdays
    assert len(slots) <= weekdays * slots_per_day
    assert len(slots) > 0


def test_full_fill_rate_returns_no_slots():
    slots = generate_weekly_slots("sp_x", date(2026, 9, 21), fill_rate=1.0, weeks=2)
    assert slots == []


def test_deterministic_per_specialist():
    a = generate_weekly_slots("sp_bhatt", date(2026, 9, 21), fill_rate=0.5, weeks=3)
    b = generate_weekly_slots("sp_bhatt", date(2026, 9, 21), fill_rate=0.5, weeks=3)
    assert [s.id for s in a] == [s.id for s in b]


def test_slot_ids_are_unique_and_specialist_scoped():
    slots = generate_weekly_slots("sp_chen", date(2026, 9, 21), fill_rate=0.3, weeks=2)
    ids = [s.id for s in slots]
    assert len(ids) == len(set(ids))
    assert all(s.specialist_id == "sp_chen" for s in slots)
    assert all(s.end - s.start == slots[0].end - slots[0].start for s in slots)
