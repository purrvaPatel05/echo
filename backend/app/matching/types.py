from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel

from app.models.enums import Urgency
from app.models.match import ClinicalFit, InsuranceCheck
from app.models.people import Patient, Specialist
from app.models.referral import ParsedCase
from app.models.scheduling import AppointmentSlot


class Candidate(BaseModel):
    """A specialist plus the logistics inputs the engine scores.

    Distance, insurance status and appointment times are supplied by other components
    (Member 3's modules); the engine treats them as plain data and never computes them.
    """

    specialist: Specialist
    distance_miles: float
    insurance: InsuranceCheck
    earliest_slot: AppointmentSlot | None = None
    days_until_slot: int | None = None


class CaseAnalyzer(Protocol):
    """The two judgments that need language understanding. Implemented by Claude and by a
    rules-only fallback."""

    async def parse_case(
        self, case_notes: str, urgency: Urgency, known_specialties: Sequence[str] = ()
    ) -> ParsedCase: ...

    async def assess_fit(
        self, parsed: ParsedCase, specialists: Sequence[Specialist]
    ) -> dict[str, ClinicalFit]:
        """Keyed by specialist id. A missing id is treated as POOR (gated out)."""
        ...


class CandidateProvider(Protocol):
    """Supplies each specialist's distance, insurance status and earliest appointment for a
    patient. Member 3's distance / insurance / scheduling modules plug in behind this."""

    async def candidates_for(
        self, patient: Patient, specialists: Sequence[Specialist]
    ) -> list[Candidate]: ...
