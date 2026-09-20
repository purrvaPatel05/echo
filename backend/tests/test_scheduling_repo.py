"""Repository-level tests for the scheduling/insurance tables and the real Booker, against an
in-memory SQLite DB (mirrors the `api` fixture's engine setup in conftest.py, but standalone
since these tests exercise the Repository/Booker directly rather than the HTTP API)."""

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.booking import SlotUnavailableError
from app.db.models import Base
from app.db.repository import Repository
from app.models.enums import InsuranceStatus
from app.models.scheduling import AppointmentSlot
from app.scheduling.booker import DbBooker


@pytest.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


def _slot(id_, specialist_id, start) -> AppointmentSlot:
    return AppointmentSlot(id=id_, specialist_id=specialist_id, start=start, end=start)


# ---- slots -----------------------------------------------------------------------------------


async def test_open_slots_excludes_booked_and_past(session_factory):
    now = datetime(2026, 9, 21, tzinfo=UTC)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_slots(
            [
                _slot("s1", "sp_a", now.replace(hour=9)),
                _slot("s2", "sp_a", now.replace(hour=10)),
                _slot("s3", "sp_a", now.replace(day=20, hour=9)),  # in the past
                _slot("s4", "sp_b", now.replace(hour=9)),  # different specialist
            ]
        )
        await repo.book_slot("s1", "ref_x")

        open_slots = await repo.open_slots("sp_a", after=now)
        assert [s.id for s in open_slots] == ["s2"]

        earliest = await repo.earliest_open_slot("sp_a", after=now)
        assert earliest.id == "s2"


async def test_create_slots_is_idempotent(session_factory):
    now = datetime(2026, 9, 21, tzinfo=UTC)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_slots([_slot("s1", "sp_a", now)])
        await repo.create_slots([_slot("s1", "sp_a", now), _slot("s2", "sp_a", now)])
        open_slots = await repo.open_slots("sp_a", after=now)
        assert {s.id for s in open_slots} == {"s1", "s2"}


# ---- booking -----------------------------------------------------------------------------------


async def test_book_slot_then_double_book_raises(session_factory):
    now = datetime(2026, 9, 21, tzinfo=UTC)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_slots([_slot("s1", "sp_a", now)])
        appt = await repo.book_slot("s1", "ref_1")
        assert appt.slot.id == "s1"
        assert appt.referral_id == "ref_1"

        with pytest.raises(SlotUnavailableError):
            await repo.book_slot("s1", "ref_2")


async def test_book_nonexistent_slot_raises(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        with pytest.raises(SlotUnavailableError):
            await repo.book_slot("does-not-exist", "ref_1")


async def test_db_booker_rejects_slot_for_wrong_specialist(session_factory):
    now = datetime(2026, 9, 21, tzinfo=UTC)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_slots([_slot("s1", "sp_a", now)])

    from app.models.referral import Referral

    booker = DbBooker(session_factory)
    referral = Referral(
        id="ref_1",
        patient_id="pat_1",
        referring_physician_id="doc_1",
        case_notes="x",
        urgency="routine",
        status="matched",
        created_at=now,
        updated_at=now,
    )
    with pytest.raises(SlotUnavailableError):
        await booker.book(referral, specialist_id="sp_wrong", slot_id="s1")

    appt = await booker.book(referral, specialist_id="sp_a", slot_id="s1")
    assert appt.slot.id == "s1"


# ---- insurance ---------------------------------------------------------------------------------


async def test_insurance_status_defaults_to_unverified(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        check = await repo.insurance_status("sp_unknown", "Aetna")
        assert check.status == InsuranceStatus.UNVERIFIED
        assert "Aetna" in check.detail


async def test_insurance_status_returns_seeded_value(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_insurance_status(
            "sp_holt", "Medicare", InsuranceStatus.OUT_OF_NETWORK, "Out-of-network"
        )
        check = await repo.insurance_status("sp_holt", "Medicare")
        assert check.status == InsuranceStatus.OUT_OF_NETWORK
        assert check.detail == "Out-of-network"


async def test_create_insurance_status_is_idempotent(session_factory):
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_insurance_status(
            "sp_holt", "Medicare", InsuranceStatus.OUT_OF_NETWORK, "first"
        )
        await repo.create_insurance_status(
            "sp_holt", "Medicare", InsuranceStatus.IN_NETWORK, "second"
        )
        check = await repo.insurance_status("sp_holt", "Medicare")
        assert check.detail == "first"  # first write wins; no duplicate row
