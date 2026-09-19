"""In-memory stand-in for Postgres. Swap for SQLAlchemy + Vultr Managed PG later.

Everything the routers touch goes through this module, so replacing it is a
one-file change.
"""
import itertools
from datetime import datetime, timedelta, timezone
from typing import Dict, List

from .models import Case, ConsultMessage, Referral, Slot, Specialist, User

_ids = itertools.count(1)


def new_id(prefix: str) -> str:
    return "%s_%d" % (prefix, next(_ids))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Mock logged-in user. Real version: Auth0/Firebase token -> user + role.
CURRENT_USER = User(
    id="u_1",
    name="Dr. Alex Rivera",
    role="referring_physician",
    city="Roanoke, VA",
    lat=37.2710,
    lng=-79.9414,
)

SPECIALISTS: Dict[str, Specialist] = {
    s.id: s
    for s in [
        Specialist(
            id="s_1", name="Dr. Priya Nair", specialty="Cardiology",
            subspecialties=["heart failure", "arrhythmia"],
            hospital="VCU Medical Center", city="Richmond, VA",
            lat=37.5407, lng=-77.4360, accepting_referrals=True,
        ),
        Specialist(
            id="s_2", name="Dr. Marcus Chen", specialty="Oncology",
            subspecialties=["breast cancer", "lung cancer"],
            hospital="UVA Cancer Center", city="Charlottesville, VA",
            lat=38.0293, lng=-78.4767, accepting_referrals=True,
        ),
        Specialist(
            id="s_3", name="Dr. Sofia Okafor", specialty="Neurology",
            subspecialties=["epilepsy", "migraine"],
            hospital="Duke University Hospital", city="Durham, NC",
            lat=35.9940, lng=-78.8986, accepting_referrals=True,
        ),
        Specialist(
            id="s_4", name="Dr. James Whitfield", specialty="Cardiology",
            subspecialties=["interventional"],
            hospital="Johns Hopkins Hospital", city="Baltimore, MD",
            lat=39.2904, lng=-76.6122, accepting_referrals=False,
        ),
        Specialist(
            id="s_5", name="Dr. Elena Petrova", specialty="Oncology",
            subspecialties=["lymphoma", "leukemia"],
            hospital="Carilion Clinic", city="Roanoke, VA",
            lat=37.2530, lng=-79.9560, accepting_referrals=True,
        ),
    ]
}


def _make_slots() -> Dict[str, Slot]:
    base = datetime.now(timezone.utc).replace(hour=14, minute=0, second=0, microsecond=0)
    slots = {}
    for spec_idx, spec_id in enumerate(SPECIALISTS):
        for day in range(1, 4):
            start = base + timedelta(days=day + spec_idx % 3)
            slot = Slot(id="slot_%s_%d" % (spec_id, day), specialist_id=spec_id, starts_at=start.isoformat())
            slots[slot.id] = slot
    return slots


SLOTS: Dict[str, Slot] = _make_slots()
CASES: Dict[str, Case] = {}
REFERRALS: Dict[str, Referral] = {}
MESSAGES: Dict[str, List[ConsultMessage]] = {}  # consult_id (== specialist id) -> messages


def reset() -> None:
    """Clear mutable state. Used by tests."""
    CASES.clear()
    REFERRALS.clear()
    MESSAGES.clear()
    SLOTS.clear()
    SLOTS.update(_make_slots())


def seed_demo_data() -> None:
    case = Case(
        id=new_id("case"), title="62F, exertional dyspnea and edema",
        patient_age=62, patient_sex="F", urgency="urgent",
        notes="Progressive shortness of breath over 3 weeks with bilateral leg edema. "
        "Elevated BNP, suspected heart failure. Echo shows reduced EF.",
        created_at=now_iso(), referring_physician_id=CURRENT_USER.id,
    )
    CASES[case.id] = case
