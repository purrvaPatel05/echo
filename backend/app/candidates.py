"""Real CandidateProvider (app.matching.types.CandidateProvider): distance, insurance-network
status, and earliest open slot per specialist -- replacing seed.fixtures.FixtureCandidateProvider.

Opens its own short-lived session per call, mirroring app/jobs.py and the Celery tasks, which
each manage their own session rather than sharing one across requests/event loops.
"""

from collections.abc import Sequence
from datetime import UTC, datetime

from app.db.repository import Repository
from app.db.session import SessionFactory
from app.integrations.maps import DistanceClient
from app.matching.types import Candidate
from app.models.people import Patient, Specialist


class RealCandidateProvider:
    def __init__(self, session_factory: SessionFactory, distance_client: DistanceClient):
        self._session_factory = session_factory
        self._distance = distance_client

    async def candidates_for(
        self, patient: Patient, specialists: Sequence[Specialist]
    ) -> list[Candidate]:
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            repo = Repository(session)
            candidates = []
            for specialist in specialists:
                distance_miles = await self._distance.distance_miles(
                    patient.location, specialist.location
                )
                insurance = await repo.insurance_status(specialist.id, patient.insurance.payer)
                slot = await repo.earliest_open_slot(specialist.id, now)
                candidates.append(
                    Candidate(
                        specialist=specialist,
                        distance_miles=distance_miles,
                        insurance=insurance,
                        earliest_slot=slot,
                        days_until_slot=(slot.start.date() - now.date()).days if slot else None,
                    )
                )
            return candidates
