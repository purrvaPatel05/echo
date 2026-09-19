"""PLACEHOLDER logistics inputs (distance, insurance status, appointment timing).

In the real system these come from Member 3's distance, insurance-verification and scheduling
modules. Until those exist, these hand-typed values let the engine run end to end in dev and
let tests pin the ranking. Replace `FixtureCandidateProvider` with theirs; nothing else changes.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta

from app.matching.types import Candidate
from app.models.enums import InsuranceStatus
from app.models.match import InsuranceCheck
from app.models.people import Patient, Specialist
from app.models.scheduling import AppointmentSlot


@dataclass(frozen=True)
class Logistics:
    distance_miles: float
    insurance: InsuranceStatus
    days_until_slot: int | None  # None = no open appointments
    plan_label: str = ""


_DETAIL = {
    InsuranceStatus.IN_NETWORK: "In-network with {plan}",
    InsuranceStatus.UNVERIFIED: "Coverage unverified, confirm with plan",
    InsuranceStatus.OUT_OF_NETWORK: "Out-of-network, patient may pay more",
    InsuranceStatus.NOT_ACCEPTED: "Does not accept this plan",
}

_IN, _OUT, _UNV, _NO = (
    InsuranceStatus.IN_NETWORK,
    InsuranceStatus.OUT_OF_NETWORK,
    InsuranceStatus.UNVERIFIED,
    InsuranceStatus.NOT_ACCEPTED,
)

# patient_id -> specialist_id -> logistics. Specialists absent for a patient are not candidates.
LOGISTICS: dict[str, dict[str, Logistics]] = {
    # Routine knee case: nearest specialist is a dermatologist (should be gated out).
    "pat_001": {
        "sp_chen": Logistics(8.4, _IN, 3),
        "sp_park": Logistics(3.0, _IN, 2),
        "sp_okafor": Logistics(0.5, _IN, 1),
    },
    # Rare neuromuscular case: distant expert vs. nearby generalist vs. irrelevant cardiologist.
    "pat_002": {
        "sp_bhatt": Logistics(42.0, _IN, 20),
        "sp_ortiz": Logistics(3.0, _IN, 5),
        "sp_novak": Logistics(1.0, _IN, 2),
    },
    # Urgent chest pain: sooner/nearer vs. better fit vs. best fit but too late.
    "pat_003": {
        "sp_adams": Logistics(18.0, _IN, 3),
        "sp_wu": Logistics(6.0, _IN, 1),
        "sp_novak": Logistics(10.0, _IN, 9),
    },
    # Rare pulmonary case: out-of-network expert (warning), in-network generalist, unaccepted.
    "pat_004": {
        "sp_holt": Logistics(12.0, _OUT, 10),
        "sp_reyes": Logistics(8.0, _IN, 6),
        "sp_lin": Logistics(5.0, _NO, 4),
    },
}


def _slot(specialist_id: str, days: int, today: date) -> AppointmentSlot:
    start = datetime.combine(today + timedelta(days=days), time(9, 0), tzinfo=UTC)
    return AppointmentSlot(
        id=f"slot_{specialist_id}_d{days}",
        specialist_id=specialist_id,
        start=start,
        end=start + timedelta(minutes=30),
    )


class FixtureCandidateProvider:
    """Dev/test stand-in for Member 3's modules."""

    def __init__(self, today: date | None = None):
        self._today = today

    async def candidates_for(
        self, patient: Patient, specialists: Sequence[Specialist]
    ) -> list[Candidate]:
        today = self._today or datetime.now(UTC).date()
        table = LOGISTICS.get(patient.id, {})
        out = []
        for sp in specialists:
            lg = table.get(sp.id)
            if lg is None:
                continue
            detail = _DETAIL[lg.insurance].format(
                plan=f"{patient.insurance.payer} {patient.insurance.plan_name}"
            )
            out.append(
                Candidate(
                    specialist=sp,
                    distance_miles=lg.distance_miles,
                    insurance=InsuranceCheck(status=lg.insurance, detail=detail),
                    earliest_slot=None
                    if lg.days_until_slot is None
                    else _slot(sp.id, lg.days_until_slot, today),
                    days_until_slot=lg.days_until_slot,
                )
            )
        return out
