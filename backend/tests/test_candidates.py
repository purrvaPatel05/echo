"""RealCandidateProvider: composes distance (injected), insurance network status, and earliest
open slot into the Candidate objects the matching engine scores. Mirrors the session-factory
fixture in test_scheduling_repo.py."""

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.candidates import RealCandidateProvider
from app.db.models import Base
from app.db.repository import Repository
from app.models.enums import InsuranceStatus
from app.models.people import GeoPoint, InsurancePlan, Patient
from app.models.scheduling import AppointmentSlot
from app.seed.data import SPECIALISTS


@pytest.fixture
async def session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


class FakeDistanceClient:
    """Deterministic stand-in for app.integrations.maps.DistanceClient."""

    async def distance_miles(self, origin, destination):
        return abs(origin.lat - destination.lat) * 100  # arbitrary, deterministic


PATIENT = Patient(
    id="pat_test",
    display_name="Test Patient",
    age=40,
    zip_code="00000",
    location=GeoPoint(lat=42.37, lng=-71.10),
    insurance=InsurancePlan(payer="Aetna", plan_name="PPO Choice"),
)

SP_CHEN = next(s for s in SPECIALISTS if s.id == "sp_chen")
SP_PARK = next(s for s in SPECIALISTS if s.id == "sp_park")


async def test_candidates_for_combines_distance_insurance_and_slots(session_factory):
    # One hour from now: always later than the real `datetime.now(UTC)` the provider computes
    # internally, and same calendar day except in the last hour before UTC midnight.
    later_today = datetime.now(UTC) + timedelta(hours=1)
    async with session_factory() as session:
        repo = Repository(session)
        await repo.create_insurance_status(
            "sp_chen", "Aetna", InsuranceStatus.IN_NETWORK, "In-network with Aetna PPO Choice"
        )
        await repo.create_slots(
            [
                AppointmentSlot(
                    id="slot1", specialist_id="sp_chen", start=later_today, end=later_today
                )
            ]
        )
        # sp_park: no insurance row (-> unverified) and no slots (-> no earliest_slot).

    provider = RealCandidateProvider(session_factory, FakeDistanceClient())
    candidates = await provider.candidates_for(PATIENT, [SP_CHEN, SP_PARK])
    by_id = {c.specialist.id: c for c in candidates}

    chen = by_id["sp_chen"]
    assert chen.insurance.status == InsuranceStatus.IN_NETWORK
    assert chen.earliest_slot is not None and chen.earliest_slot.id == "slot1"
    assert chen.days_until_slot == 0
    expected_distance = abs(PATIENT.location.lat - SP_CHEN.location.lat) * 100
    assert chen.distance_miles == pytest.approx(expected_distance)

    park = by_id["sp_park"]
    assert park.insurance.status == InsuranceStatus.UNVERIFIED
    assert park.earliest_slot is None
    assert park.days_until_slot is None
