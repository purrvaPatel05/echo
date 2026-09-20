"""Demo scenarios that pin expected ranking behavior.

Candidate logistics (distance, insurance, days) come from app.seed.fixtures; the clinical-fit
tiers below are what Claude is scripted to return.
"""

from dataclasses import dataclass, field

from app.models.enums import Complexity, FitTier, Urgency, WeightProfile


@dataclass(frozen=True)
class Scenario:
    id: str
    patient_id: str
    urgency: Urgency
    complexity: Complexity
    fits: dict[str, FitTier]
    expected_order: list[str]
    expected_too_late: list[str] = field(default_factory=list)
    expected_profile: WeightProfile = WeightProfile.ROUTINE


SCENARIOS = [
    Scenario(
        id="closest_specialist_gated_out",
        patient_id="pat_001",
        urgency=Urgency.ROUTINE,
        complexity=Complexity.ROUTINE,
        fits={"sp_chen": FitTier.EXCELLENT, "sp_park": FitTier.GOOD, "sp_okafor": FitTier.POOR},
        expected_order=["sp_chen", "sp_park"],
    ),
    Scenario(
        id="rare_case_distant_expert_still_wins",
        patient_id="pat_002",
        urgency=Urgency.ROUTINE,
        complexity=Complexity.RARE_COMPLEX,
        fits={"sp_bhatt": FitTier.EXCELLENT, "sp_ortiz": FitTier.PARTIAL, "sp_novak": FitTier.POOR},
        expected_order=["sp_bhatt", "sp_ortiz"],
        expected_profile=WeightProfile.RARE_COMPLEX,
    ),
    Scenario(
        id="urgent_nearby_sooner_beats_better_fit",
        patient_id="pat_003",
        urgency=Urgency.URGENT,
        complexity=Complexity.ROUTINE,
        fits={
            "sp_adams": FitTier.EXCELLENT,
            "sp_wu": FitTier.GOOD,
            "sp_novak": FitTier.EXCELLENT,
        },
        expected_order=["sp_wu", "sp_adams"],
        expected_too_late=["sp_novak"],
        expected_profile=WeightProfile.URGENT,
    ),
    Scenario(
        id="out_of_network_expert_surfaced_with_warning",
        patient_id="pat_004",
        urgency=Urgency.ROUTINE,
        complexity=Complexity.RARE_COMPLEX,
        fits={"sp_holt": FitTier.EXCELLENT, "sp_reyes": FitTier.GOOD, "sp_lin": FitTier.EXCELLENT},
        expected_order=["sp_holt", "sp_reyes"],  # sp_lin: plan not accepted -> excluded
        expected_profile=WeightProfile.RARE_COMPLEX,
    ),
]
