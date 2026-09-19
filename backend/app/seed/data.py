"""Synthetic people and demo cases. Nothing here is real; never add real patient data."""

from dataclasses import dataclass

from app.models.enums import Urgency
from app.models.people import GeoPoint, InsurancePlan, Patient, Physician, Specialist

PHYSICIANS = [
    Physician(
        id="doc_001",
        name="Dr. Elena Ruiz",
        specialty="Family Medicine",
        practice_name="Riverside Family Practice",
    ),
    Physician(
        id="doc_002",
        name="Dr. Marcus Bell",
        specialty="Internal Medicine",
        practice_name="Harbor Internal Medicine",
    ),
    Physician(
        id="doc_003",
        name="Dr. Hannah Cho",
        specialty="Family Medicine",
        practice_name="Maple Street Clinic",
    ),
]


def _patient(id_, name, age, zip_code, lat, lng, payer, plan) -> Patient:
    return Patient(
        id=id_,
        display_name=name,
        age=age,
        zip_code=zip_code,
        location=GeoPoint(lat=lat, lng=lng),
        insurance=InsurancePlan(payer=payer, plan_name=plan),
    )


PATIENTS = [
    _patient("pat_001", "Maria Lopez", 58, "02139", 42.3644, -71.1032, "Aetna", "PPO Choice"),
    _patient("pat_002", "James Carter", 34, "02446", 42.3418, -71.1212, "Blue Cross", "HMO Blue"),
    _patient("pat_003", "Priya Shah", 45, "02115", 42.3429, -71.0995, "Cigna", "Open Access Plus"),
    _patient("pat_004", "Robert Kim", 67, "02138", 42.3770, -71.1167, "Medicare", "Advantage Plan"),
    _patient("pat_005", "Aisha Khan", 29, "02143", 42.3876, -71.0995, "UnitedHealthcare", "Choice"),
    _patient("pat_006", "Tom Nguyen", 51, "02472", 42.3709, -71.1828, "Aetna", "PPO Choice"),
]


def _specialist(id_, name, specialty, subs, practice, address, lat, lng) -> Specialist:
    return Specialist(
        id=id_,
        name=name,
        specialty=specialty,
        subspecialties=subs,
        practice_name=practice,
        address=address,
        location=GeoPoint(lat=lat, lng=lng),
    )


SPECIALISTS = [
    _specialist(
        "sp_chen",
        "Dr. Sarah Chen",
        "Orthopedics",
        ["knee", "sports medicine"],
        "Charles River Orthopedics",
        "120 Main St, Cambridge, MA",
        42.3736,
        -71.1097,
    ),
    _specialist(
        "sp_park",
        "Dr. David Park",
        "Orthopedics",
        ["shoulder", "sports medicine"],
        "Back Bay Bone & Joint",
        "45 Newbury St, Boston, MA",
        42.3505,
        -71.0810,
    ),
    _specialist(
        "sp_okafor",
        "Dr. Ngozi Okafor",
        "Dermatology",
        ["medical dermatology"],
        "Cambridge Skin Clinic",
        "18 Broadway, Cambridge, MA",
        42.3651,
        -71.1040,
    ),
    _specialist(
        "sp_ortiz",
        "Dr. Luis Ortiz",
        "Neurology",
        ["general neurology", "headache"],
        "Neighborhood Neurology",
        "9 Elm St, Newton, MA",
        42.3370,
        -71.2092,
    ),
    _specialist(
        "sp_bhatt",
        "Dr. Anita Bhatt",
        "Neurology",
        ["neuromuscular", "myopathy", "rare neurogenetic disorders"],
        "New England Neuromuscular Center",
        "800 Research Way, Worcester, MA",
        42.2626,
        -71.8023,
    ),
    _specialist(
        "sp_wu",
        "Dr. Kevin Wu",
        "Cardiology",
        ["interventional cardiology", "chest pain"],
        "Beacon Heart Institute",
        "60 Fenwood Rd, Boston, MA",
        42.3352,
        -71.1049,
    ),
    _specialist(
        "sp_adams",
        "Dr. Renee Adams",
        "Cardiology",
        ["chest pain", "preventive cardiology"],
        "Suburban Cardiology Group",
        "300 Route 9, Framingham, MA",
        42.2793,
        -71.4162,
    ),
    _specialist(
        "sp_novak",
        "Dr. Peter Novak",
        "Cardiology",
        ["electrophysiology", "arrhythmia"],
        "Cambridge Heart Rhythm Clinic",
        "2 Kendall Sq, Cambridge, MA",
        42.3662,
        -71.0906,
    ),
    _specialist(
        "sp_reyes",
        "Dr. Carla Reyes",
        "Pulmonology",
        ["general pulmonology", "asthma"],
        "Allston Pulmonary Associates",
        "77 Harvard Ave, Boston, MA",
        42.3539,
        -71.1337,
    ),
    _specialist(
        "sp_holt",
        "Dr. Julian Holt",
        "Pulmonology",
        ["pulmonary hypertension", "pulmonary"],
        "Pulmonary Vascular Center",
        "1 Longwood Ave, Boston, MA",
        42.3376,
        -71.1058,
    ),
    _specialist(
        "sp_lin",
        "Dr. Grace Lin",
        "Pulmonology",
        ["sleep medicine", "pulmonary"],
        "Sleep & Lung Care",
        "12 Beacon St, Brookline, MA",
        42.3430,
        -71.1210,
    ),
    _specialist(
        "sp_meyer",
        "Dr. Sam Meyer",
        "Endocrinology",
        ["thyroid", "diabetes"],
        "Greater Boston Endocrine",
        "55 State St, Boston, MA",
        42.3588,
        -71.0567,
    ),
]


@dataclass(frozen=True)
class DemoCase:
    referral_id: str
    patient_id: str
    physician_id: str
    urgency: Urgency
    notes: str


DEMO_CASES = [
    DemoCase(
        "ref_demo_knee",
        "pat_001",
        "doc_001",
        Urgency.ROUTINE,
        "58F, 3 months progressive right knee pain, worse on stairs. Swelling after "
        "activity. No trauma. X-ray shows joint space narrowing.",
    ),
    DemoCase(
        "ref_demo_rare_neuro",
        "pat_002",
        "doc_002",
        Urgency.ROUTINE,
        "34M with progressive proximal muscle weakness over 8 months and persistently "
        "elevated CK. Initial workup nondiagnostic. Family history of an undiagnosed "
        "neuromuscular disorder. Suspect a rare inherited or inflammatory myopathy.",
    ),
    DemoCase(
        "ref_demo_urgent_chest",
        "pat_003",
        "doc_001",
        Urgency.SOON,
        "45F with sudden chest pain radiating to the left arm on exertion for 2 days, "
        "worsening. Abnormal ECG with ST changes. Needs cardiology evaluation.",
    ),
    DemoCase(
        "ref_demo_rare_pulm",
        "pat_004",
        "doc_003",
        Urgency.ROUTINE,
        "67M with refractory pulmonary arterial hypertension despite standard therapy, "
        "worsening dyspnea and exercise intolerance. Considering advanced or "
        "investigational options.",
    ),
    DemoCase(
        "ref_demo_derm",
        "pat_005",
        "doc_003",
        Urgency.ROUTINE,
        "29F with a persistent scaly rash on both elbows for 4 months, suspected "
        "psoriasis. Not responding to over-the-counter steroid cream.",
    ),
    DemoCase(
        "ref_demo_thyroid",
        "pat_006",
        "doc_002",
        Urgency.ROUTINE,
        "51M with fatigue and weight gain, TSH markedly elevated on two occasions. "
        "Requesting thyroid evaluation.",
    ),
]
