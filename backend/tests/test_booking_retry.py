"""Booking is safe to retry (HANDOFF.md, request 1).

Booking commits the appointment first; the referral is saved as booked in a separate step. If
that second step fails, the slot stays taken by *this* referral, and the physician's retry must
succeed with the same appointment instead of getting a 409.
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.booking import SlotUnavailableError
from app.candidates import RealCandidateProvider
from app.db.models import AppointmentRow, Base
from app.db.repository import Repository
from app.models.scheduling import AppointmentSlot
from app.scheduling.booker import DbBooker


class FakeDistanceClient:
    async def distance_miles(self, origin, destination):
        return 5.0


@pytest.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    start = datetime.now(UTC) + timedelta(days=2)
    async with factory() as session:
        await Repository(session).create_slots(
            [AppointmentSlot(id="slot_1", specialist_id="sp_a", start=start, end=start)]
        )
    yield factory
    await engine.dispose()


async def _appointments(factory, slot_id="slot_1") -> int:
    async with factory() as session:
        return await session.scalar(
            select(func.count())
            .select_from(AppointmentRow)
            .where(AppointmentRow.slot_id == slot_id)
        )


# ---- repository ----------------------------------------------------------------------------------


async def test_rebooking_the_same_slot_for_the_same_referral_returns_the_same_appointment(
    session_factory,
):
    async with session_factory() as session:
        first = await Repository(session).book_slot("slot_1", "ref_a")
    async with session_factory() as session:
        again = await Repository(session).book_slot("slot_1", "ref_a")
    assert again.id == first.id and again.slot == first.slot and again.referral_id == "ref_a"
    assert await _appointments(session_factory) == 1  # nothing was booked twice


async def test_a_different_referral_still_cannot_take_a_held_slot(session_factory):
    async with session_factory() as session:
        await Repository(session).book_slot("slot_1", "ref_a")
    async with session_factory() as session:
        with pytest.raises(SlotUnavailableError):
            await Repository(session).book_slot("slot_1", "ref_b")
    assert await _appointments(session_factory) == 1


async def test_unknown_slot_is_still_unavailable(session_factory):
    async with session_factory() as session:
        with pytest.raises(SlotUnavailableError):
            await Repository(session).book_slot("nope", "ref_a")


async def test_two_simultaneous_retries_for_one_referral_make_one_booking(tmp_path):
    # A real file database, so the two attempts get separate connections (the in-memory fixture
    # above shares one, where one attempt's rollback would also undo the other's insert).
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'race.db'}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    start = datetime.now(UTC) + timedelta(days=2)
    async with factory() as session:
        await Repository(session).create_slots(
            [AppointmentSlot(id="slot_1", specialist_id="sp_a", start=start, end=start)]
        )
    booker = DbBooker(factory)

    class R:  # the booker only reads `.id`
        id = "ref_a"

    results = await asyncio.gather(
        *(booker.book(R, "sp_a", "slot_1") for _ in range(4)), return_exceptions=True
    )
    assert not [r for r in results if isinstance(r, Exception)], results
    assert len({r.id for r in results}) == 1
    assert await _appointments(factory) == 1
    await engine.dispose()


# ---- through the API: the failure HANDOFF.md describes ------------------------------


class CrashAfterBooking:
    """Books for real, then fails before the referral is saved: the gap the report describes."""

    def __init__(self, inner):
        self.inner, self.calls = inner, 0

    async def book(self, referral, specialist_id, slot_id):
        appointment = await self.inner.book(referral, specialist_id, slot_id)
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("connection dropped after the booking committed")
        return appointment


async def _matched(api):
    api.state["provider"] = RealCandidateProvider(api.factory, FakeDistanceClient())
    c = api.client
    ref = "ref_demo_knee"
    assert (await c.post(f"/referrals/{ref}/parse")).status_code == 202
    assert (await c.patch(f"/referrals/{ref}", json={"complexity": "routine"})).status_code == 200
    assert (await c.post(f"/referrals/{ref}/match")).status_code == 202
    run = (await c.get(f"/referrals/{ref}/match")).json()
    top = run["results"][0]
    body = {
        "match_run_id": run["id"],
        "specialist_id": top["specialist"]["id"],
        "slot_id": top["earliest_slot"]["id"],
    }
    return ref, body


async def test_core_approve_retry_after_a_failure_between_booking_and_saving(api):
    ref, body = await _matched(api)
    api.state["booker"] = CrashAfterBooking(DbBooker(api.factory))
    c = api.client

    with pytest.raises(RuntimeError):  # first attempt: the booking committed, then it fell over
        await c.post(f"/referrals/{ref}/approve", json=body)
    stuck = (await c.get(f"/referrals/{ref}")).json()
    assert stuck["status"] == "matched" and stuck["appointment"] is None  # the reported state
    assert await _appointments(api.factory, body["slot_id"]) == 1  # ...with the slot taken

    retry = await c.post(f"/referrals/{ref}/approve", json=body)  # the physician tries again
    assert retry.status_code == 200, retry.text
    done = retry.json()
    assert done["status"] == "booked" and done["appointment"]["slot"]["id"] == body["slot_id"]
    assert await _appointments(api.factory, body["slot_id"]) == 1  # still one booking


async def test_echo_approve_retry_after_the_same_failure(api):
    api.state["provider"] = RealCandidateProvider(api.factory, FakeDistanceClient())
    api.state["booker"] = CrashAfterBooking(DbBooker(api.factory))
    c = api.client
    form = {
        "patientId": "pat_001",
        "patientLocation": "Cambridge, MA",
        "insurance": "Aetna",
        "specialty": "Orthopedics",
        "subspecialty": "Knee",
        "preferredDistanceMiles": 25,
        "urgency": "soon",
        "reason": "Knee pain",
        "details": "Right knee pain for 6 weeks, locking on stairs.",
    }
    rid = (await c.post("/api/echo/referrals", json=form)).json()["id"]
    sp = (await c.get(f"/api/echo/referrals/{rid}/matches")).json()["matches"][0]["specialist"][
        "id"
    ]
    slot = (await c.get(f"/api/echo/specialists/{sp}/slots")).json()[0]
    body = {"specialistId": sp, "slotId": slot["id"]}

    with pytest.raises(RuntimeError):
        await c.post(f"/api/echo/referrals/{rid}/approve", json=body)
    retry = await c.post(f"/api/echo/referrals/{rid}/approve", json=body)
    assert retry.status_code == 200 and retry.json()["status"] == "scheduled"
    assert await _appointments(api.factory, slot["id"]) == 1
