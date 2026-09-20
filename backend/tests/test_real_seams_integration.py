"""End-to-end: the real RealCandidateProvider + DbBooker wired into the referral flow via the
`api` fixture's dependency overrides, replacing FixtureCandidateProvider/FakeBooker used
elsewhere. Confirms the seams Member 3 owns actually compose through parse -> confirm -> match ->
approve -> book, not just in isolation (see test_scheduling_repo.py / test_candidates.py)."""

from datetime import UTC, datetime, timedelta

from app.candidates import RealCandidateProvider
from app.db.repository import Repository
from app.models.enums import InsuranceStatus
from app.models.scheduling import AppointmentSlot
from app.scheduling.booker import DbBooker

KNEE = "ref_demo_knee"
KNEE_DOC = "doc_001"


class FakeDistanceClient:
    async def distance_miles(self, origin, destination):
        return 5.0


async def _seed_logistics(factory):
    async with factory() as session:
        repo = Repository(session)
        for specialist_id in ("sp_chen", "sp_park"):
            await repo.create_insurance_status(
                specialist_id, "Aetna", InsuranceStatus.IN_NETWORK, "In-network with Aetna"
            )
            start = datetime.now(UTC) + timedelta(days=3)
            await repo.create_slots(
                [
                    AppointmentSlot(
                        id=f"slot_{specialist_id}_test",
                        specialist_id=specialist_id,
                        start=start,
                        end=start + timedelta(minutes=30),
                    )
                ]
            )


async def test_real_provider_and_booker_book_a_real_slot(api):
    await _seed_logistics(api.factory)
    api.state["provider"] = RealCandidateProvider(api.factory, FakeDistanceClient())
    api.state["booker"] = DbBooker(api.factory)

    c = api.client
    await c.post(f"/referrals/{KNEE}/parse")
    await c.patch(f"/referrals/{KNEE}", json={"complexity": "routine"})
    run = (await c.post(f"/referrals/{KNEE}/match")).json()
    run = (await c.get(f"/referrals/{KNEE}/match")).json()
    assert run["status"] == "complete"
    top = run["results"][0]
    assert top["specialist"]["id"] == "sp_chen"

    approve = await c.post(
        f"/referrals/{KNEE}/approve",
        json={
            "match_run_id": run["id"],
            "specialist_id": top["specialist"]["id"],
            "slot_id": top["earliest_slot"]["id"],
            "approved_by": KNEE_DOC,
        },
    )
    assert approve.status_code == 200
    body = approve.json()
    assert body["status"] == "booked"
    assert body["appointment"]["slot"]["id"] == top["earliest_slot"]["id"]

    # the slot is really gone: booking it again for a different referral fails
    async with api.factory() as session:
        repo = Repository(session)
        again = await repo.open_slots("sp_chen", after=datetime.now(UTC))
        assert top["earliest_slot"]["id"] not in [s.id for s in again]
